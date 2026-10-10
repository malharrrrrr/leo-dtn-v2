"""Deterministic, contact-aware discrete-event simulation engine."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from dataclasses import replace
from enum import IntEnum

from .model import (
    ActiveTransmissionSnapshot,
    BufferSample,
    BundleRequest,
    BundleSnapshot,
    BundleStatus,
    Contact,
    ContactInterruption,
    EventRecord,
    ForwardingRecord,
    Node,
    NodeSnapshot,
    SimulationSnapshot,
)
from .orbit import position_and_velocity_ecef
from .routing import ContactAwareEarliestArrival, RoutingPolicy, serialization_duration_us


class EventPriority(IntEnum):
    EXPIRATION = 0
    CONTACT_END = 10
    CONTACT_START = 20
    TRANSMISSION_COMPLETE = 30
    RECEIVER_ARRIVAL = 40
    BUNDLE_GENERATION = 50
    ROUTE = 60


@dataclass(order=True, frozen=True, slots=True)
class _ScheduledEvent:
    time_us: int
    priority: int
    queue_sequence: int
    kind: str = field(compare=False)
    bundle_id: str | None = field(default=None, compare=False)
    contact_id: str | None = field(default=None, compare=False)
    attempt: int = field(default=0, compare=False)


@dataclass(slots=True)
class _Bundle:
    request: BundleRequest
    expiry_time_us: int
    holder: str | None
    status: BundleStatus
    queued_at_us: int | None = None
    history: list[ForwardingRecord] = field(default_factory=list)
    visited: set[str] = field(default_factory=set)
    attempt: int = 0


@dataclass(slots=True)
class _BundleStream:
    template: BundleRequest
    interval_us: int
    stream_id: str
    next_index: int = 2


class SimulationEngine:
    """Owns all mutable state for one deterministic simulation run."""

    def __init__(
        self,
        *,
        nodes: tuple[Node, ...],
        contacts: tuple[Contact, ...],
        interruptions: tuple[ContactInterruption, ...] = (),
        routing_policy: RoutingPolicy | None = None,
    ) -> None:
        self._nodes = self._validate_nodes(nodes)
        self._contacts = self._validate_contacts(contacts, self._nodes)
        self._contacts_by_id = {contact.contact_id: contact for contact in self._contacts}
        self._routing_policy = (
            routing_policy if routing_policy is not None else ContactAwareEarliestArrival()
        )
        if not isinstance(getattr(self._routing_policy, "name", None), str) or not self._routing_policy.name:
            raise ValueError("routing policy must have a non-empty name")
        self._occupancy = {node_id: 0 for node_id in self._nodes}
        self._bundles: dict[str, _Bundle] = {}
        self._requests: dict[str, BundleRequest] = {}
        self._bundle_streams: dict[str, _BundleStream] = {}
        self._active_by_contact: dict[str, str] = {}
        self._active_transmissions: dict[str, ActiveTransmissionSnapshot] = {}
        self._contact_cutoffs: dict[str, int] = {}
        self._queue: list[_ScheduledEvent] = []
        self._queue_sequence = 0
        self._events_processed = 0
        self._record_sequence = 0
        self._time_us = 0
        self._records: list[EventRecord] = []
        self._dispatch_scheduled: set[int] = set()
        self._buffer_samples = [
            BufferSample(time_us=0, node_id=node_id, occupancy_bytes=0)
            for node_id in sorted(self._nodes)
        ]

        for contact in self._contacts:
            self._schedule(contact.start_us, EventPriority.CONTACT_START, "contact_start", contact_id=contact.contact_id)
            self._schedule(contact.end_us, EventPriority.CONTACT_END, "contact_end", contact_id=contact.contact_id)

        if any(
            not isinstance(item.time_us, int) or isinstance(item.time_us, bool)
            for item in interruptions
        ):
            raise ValueError("contact interruption time must be integer microseconds")
        seen_interruptions: set[str] = set()
        for interruption in sorted(interruptions, key=lambda item: (item.time_us, item.contact_id)):
            contact = self._contacts_by_id.get(interruption.contact_id)
            if contact is None:
                raise ValueError(f"interruption references unknown contact {interruption.contact_id}")
            if (
                not isinstance(interruption.time_us, int)
                or isinstance(interruption.time_us, bool)
                or not contact.start_us < interruption.time_us < contact.end_us
            ):
                raise ValueError("contact interruption must occur strictly inside its contact window")
            if interruption.contact_id in seen_interruptions:
                raise ValueError("only one interruption per contact is supported")
            seen_interruptions.add(interruption.contact_id)
            self._schedule(
                interruption.time_us,
                EventPriority.CONTACT_END,
                "contact_interruption",
                contact_id=interruption.contact_id,
            )

    @staticmethod
    def _validate_nodes(nodes: tuple[Node, ...]) -> dict[str, Node]:
        by_id: dict[str, Node] = {}
        for node in nodes:
            if not node.node_id or node.node_id in by_id:
                raise ValueError("node IDs must be non-empty and unique")
            if (
                not isinstance(node.buffer_capacity_bytes, int)
                or isinstance(node.buffer_capacity_bytes, bool)
                or node.buffer_capacity_bytes < 0
            ):
                raise ValueError(f"node {node.node_id} buffer capacity must be a nonnegative integer")
            if node.position_km is not None and (
                len(node.position_km) != 3
                or any(
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    for value in node.position_km
                )
            ):
                raise ValueError(f"node {node.node_id} position must contain three coordinates")
            if node.orbit is not None:
                orbit_values = (node.orbit.altitude_km, node.orbit.inclination_deg, node.orbit.raan_deg, node.orbit.phase_deg)
                if node.kind.value != "satellite" or any(not math.isfinite(value) for value in orbit_values):
                    raise ValueError(f"node {node.node_id} has invalid orbital elements")
                if not 100 <= node.orbit.altitude_km <= 2_000 or not 0 <= node.orbit.inclination_deg <= 180:
                    raise ValueError(f"node {node.node_id} orbit is outside the supported circular LEO model")
            by_id[node.node_id] = node
        if not by_id:
            raise ValueError("at least one node is required")
        return by_id

    @staticmethod
    def _validate_contacts(
        contacts: tuple[Contact, ...], nodes: dict[str, Node]
    ) -> tuple[Contact, ...]:
        for contact in contacts:
            timestamps = (contact.start_us, contact.end_us, contact.propagation_delay_us)
            if any(not isinstance(value, int) or isinstance(value, bool) for value in timestamps):
                raise ValueError(f"contact {contact.contact_id} timestamps must be integer microseconds")
            if (
                not isinstance(contact.rate_bits_per_second, int)
                or isinstance(contact.rate_bits_per_second, bool)
            ):
                raise ValueError(f"contact {contact.contact_id} data rate must be an integer")
        ids: set[str] = set()
        ordered = tuple(sorted(contacts, key=lambda item: (item.from_node, item.to_node, item.start_us, item.contact_id)))
        previous_by_pair: dict[tuple[str, str], Contact] = {}
        for contact in ordered:
            if not contact.contact_id or contact.contact_id in ids:
                raise ValueError("contact IDs must be non-empty and unique")
            ids.add(contact.contact_id)
            if contact.from_node not in nodes or contact.to_node not in nodes:
                raise ValueError(f"contact {contact.contact_id} references an unknown node")
            if contact.from_node == contact.to_node:
                raise ValueError(f"contact {contact.contact_id} cannot connect a node to itself")
            if contact.start_us < 0 or contact.start_us >= contact.end_us:
                raise ValueError(f"contact {contact.contact_id} must have start < end and nonnegative times")
            if (
                not isinstance(contact.rate_bits_per_second, int)
                or isinstance(contact.rate_bits_per_second, bool)
                or contact.rate_bits_per_second <= 0
                or contact.propagation_delay_us < 0
            ):
                raise ValueError(f"contact {contact.contact_id} has invalid rate or propagation delay")
            pair = (contact.from_node, contact.to_node)
            previous = previous_by_pair.get(pair)
            if previous is not None and contact.start_us < previous.end_us:
                raise ValueError(f"contacts {previous.contact_id} and {contact.contact_id} overlap")
            previous_by_pair[pair] = contact
        return ordered

    @property
    def time_us(self) -> int:
        return self._time_us

    @property
    def next_event_time_us(self) -> int | None:
        return self._queue[0].time_us if self._queue else None

    @property
    def events_processed(self) -> int:
        return self._events_processed

    def add_bundle(self, request: BundleRequest) -> None:
        """Schedule one bundle generation attempt without mutating state immediately."""
        if not request.bundle_id:
            raise ValueError("bundle ID must be non-empty")
        if request.bundle_id in self._bundles or any(
            event.bundle_id == request.bundle_id for event in self._queue
        ):
            raise ValueError(f"duplicate bundle ID: {request.bundle_id}")
        if request.source not in self._nodes or request.destination not in self._nodes:
            raise ValueError("bundle source and destination must be known nodes")
        if request.source == request.destination:
            raise ValueError("bundle source and destination must differ")
        integer_values = (request.payload_bytes, request.creation_time_us, request.ttl_us)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in integer_values):
            raise ValueError("bundle size, creation time, and TTL must be integer values")
        if request.payload_bytes <= 0 or request.ttl_us <= 0:
            raise ValueError("bundle size and TTL must be positive")
        if request.creation_time_us < self._time_us:
            raise ValueError("bundle creation time cannot be in the past")
        self._schedule(
            request.creation_time_us,
            EventPriority.BUNDLE_GENERATION,
            "bundle_generation",
            bundle_id=request.bundle_id,
        )
        # Keep the immutable request separately until its generation event.
        self._requests[request.bundle_id] = request

    def add_recurring_bundle(self, request: BundleRequest, *, interval_us: int) -> None:
        """Schedule a repeatable traffic source using one configured bundle as template."""
        if not isinstance(interval_us, int) or isinstance(interval_us, bool) or interval_us <= 0:
            raise ValueError("bundle generation interval must be a positive integer")
        self.add_bundle(request)
        self._bundle_streams[request.bundle_id] = _BundleStream(
            request, interval_us, request.bundle_id
        )

    def _schedule(
        self,
        time_us: int,
        priority: EventPriority,
        kind: str,
        *,
        bundle_id: str | None = None,
        contact_id: str | None = None,
        attempt: int = 0,
    ) -> None:
        if time_us < self._time_us:
            raise ValueError("cannot schedule an event in the past")
        heapq.heappush(
            self._queue,
            _ScheduledEvent(time_us, int(priority), self._queue_sequence, kind, bundle_id, contact_id, attempt),
        )
        self._queue_sequence += 1

    def step(self) -> EventRecord | None:
        """Process one event, including any event at the current simulation tick."""
        if not self._queue:
            return None
        event = heapq.heappop(self._queue)
        self._time_us = event.time_us
        self._events_processed += 1
        previous_record_count = len(self._records)
        self._process(event)
        if event.kind == "dispatch":
            self._dispatch_scheduled.discard(event.time_us)
        return self._records[-1] if len(self._records) > previous_record_count else None

    def run_until(
        self, horizon_us: int, *, max_events: int | None = None
    ) -> SimulationSnapshot:
        if not isinstance(horizon_us, int) or isinstance(horizon_us, bool):
            raise ValueError("simulation horizon must be integer microseconds")
        if horizon_us < self._time_us:
            raise ValueError("simulation horizon cannot be in the past")
        if max_events is not None and (
            not isinstance(max_events, int) or isinstance(max_events, bool) or max_events < 0
        ):
            raise ValueError("max_events must be a nonnegative integer")
        processed = 0
        while (
            self._queue
            and self._queue[0].time_us <= horizon_us
            and (max_events is None or processed < max_events)
        ):
            self.step()
            processed += 1
        if self.next_event_time_us is None or self.next_event_time_us > horizon_us:
            self._time_us = horizon_us
        return self.snapshot()

    def run_to_completion(self) -> SimulationSnapshot:
        while self._queue:
            self.step()
        return self.snapshot()

    def extend_contact_plan(self, contacts: tuple[Contact, ...]) -> None:
        """Merge a regenerated orbital plan, extending open windows in place.

        Contact IDs are stable across plans regenerated from epoch zero. An end
        event from an earlier, shorter plan is left in the heap and ignored when
        it becomes stale; this keeps event queue mutation deterministic.
        """
        candidates = self._validate_contacts(contacts, self._nodes)
        by_id = {contact.contact_id: contact for contact in self._contacts}
        for candidate in candidates:
            existing = by_id.get(candidate.contact_id)
            if existing is not None:
                if (
                    existing.from_node != candidate.from_node
                    or existing.to_node != candidate.to_node
                    or existing.start_us != candidate.start_us
                    or existing.rate_bits_per_second != candidate.rate_bits_per_second
                    or existing.propagation_delay_us != candidate.propagation_delay_us
                ):
                    raise ValueError(f"regenerated contact {candidate.contact_id} changed identity")
                if candidate.end_us > existing.end_us and candidate.end_us > self._time_us:
                    by_id[candidate.contact_id] = candidate
                    self._schedule(candidate.end_us, EventPriority.CONTACT_END, "contact_end", contact_id=candidate.contact_id)
                    if existing.end_us <= self._time_us and candidate.start_us <= self._time_us:
                        self._schedule_route_at_current_time()
                continue
            if candidate.end_us <= self._time_us:
                continue
            by_id[candidate.contact_id] = candidate
            if candidate.start_us >= self._time_us:
                self._schedule(candidate.start_us, EventPriority.CONTACT_START, "contact_start", contact_id=candidate.contact_id)
            else:
                self._schedule_route_at_current_time()
            self._schedule(candidate.end_us, EventPriority.CONTACT_END, "contact_end", contact_id=candidate.contact_id)
        merged = self._validate_contacts(tuple(by_id.values()), self._nodes)
        self._contacts = merged
        self._contacts_by_id = {contact.contact_id: contact for contact in merged}

    def _schedule_route_at_current_time(self) -> None:
        if any(bundle.status == BundleStatus.QUEUED for bundle in self._bundles.values()):
            self._schedule_route("contact-plan-update", self._time_us)

    def _record(
        self,
        kind: str,
        *,
        bundle_id: str | None = None,
        node_id: str | None = None,
        contact_id: str | None = None,
        details: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self._records.append(
            EventRecord(
                sequence=self._record_sequence,
                time_us=self._time_us,
                kind=kind,
                bundle_id=bundle_id,
                node_id=node_id,
                contact_id=contact_id,
                details=details,
            )
        )
        self._record_sequence += 1

    def _process(self, event: _ScheduledEvent) -> None:
        if event.kind == "contact_start":
            self._record("contact_started", contact_id=event.contact_id)
        elif event.kind == "contact_end":
            self._handle_contact_end(event.contact_id, event.time_us)
        elif event.kind == "contact_interruption":
            self._handle_contact_interruption(event.contact_id)
        elif event.kind == "bundle_generation":
            self._handle_generation(event.bundle_id)
        elif event.kind == "bundle_expiration":
            self._handle_expiration(event.bundle_id)
        elif event.kind == "dispatch":
            self._handle_dispatch()
        elif event.kind == "transmission_complete":
            self._handle_transmission_complete(event)
        elif event.kind == "receiver_arrival":
            self._handle_receiver_arrival(event)
        else:
            raise RuntimeError(f"unknown event type: {event.kind}")

    def _handle_generation(self, bundle_id: str | None) -> None:
        assert bundle_id is not None
        request = self._requests[bundle_id]
        expiry = request.creation_time_us + request.ttl_us
        source = self._nodes[request.source]
        self._bundles[bundle_id] = _Bundle(
            request=request,
            expiry_time_us=expiry,
            holder=None,
            status=BundleStatus.REJECTED_AT_SOURCE,
        )
        self._schedule(expiry, EventPriority.EXPIRATION, "bundle_expiration", bundle_id=bundle_id)
        self._record("bundle_generated", bundle_id=bundle_id, node_id=request.source)
        self._schedule_next_stream_bundle(bundle_id)
        if self._occupancy[request.source] + request.payload_bytes > source.buffer_capacity_bytes:
            self._record("bundle_rejected_at_source", bundle_id=bundle_id, node_id=request.source)
            return
        bundle = self._bundles[bundle_id]
        bundle.status = BundleStatus.QUEUED
        bundle.holder = request.source
        bundle.queued_at_us = self._time_us
        bundle.visited.add(request.source)
        self._change_occupancy(request.source, request.payload_bytes)
        self._record("bundle_queued", bundle_id=bundle_id, node_id=request.source)
        self._schedule_route(bundle_id, self._time_us)

    def _schedule_next_stream_bundle(self, template_id: str) -> None:
        stream = self._bundle_streams.pop(template_id, None)
        if stream is None:
            return
        while True:
            bundle_id = f"{stream.stream_id}-AUTO-{stream.next_index:06d}"
            stream.next_index += 1
            if bundle_id not in self._requests:
                break
        template = stream.template
        request = BundleRequest(
            bundle_id=bundle_id,
            source=template.source,
            destination=template.destination,
            payload_bytes=template.payload_bytes,
            creation_time_us=self._time_us + stream.interval_us,
            ttl_us=template.ttl_us,
        )
        self._requests[bundle_id] = request
        self._schedule(
            request.creation_time_us,
            EventPriority.BUNDLE_GENERATION,
            "bundle_generation",
            bundle_id=bundle_id,
        )
        self._bundle_streams[bundle_id] = stream

    def _handle_expiration(self, bundle_id: str | None) -> None:
        if bundle_id is None:
            return
        bundle = self._bundles.get(bundle_id)
        if bundle is None or bundle.status in (
            BundleStatus.DELIVERED,
            BundleStatus.EXPIRED,
            BundleStatus.REJECTED_AT_SOURCE,
        ):
            return
        if bundle.holder is not None:
            self._change_occupancy(bundle.holder, -bundle.request.payload_bytes)
        active_contact = next(
            (cid for cid, bid in self._active_by_contact.items() if bid == bundle_id), None
        )
        if active_contact is not None:
            del self._active_by_contact[active_contact]
            self._active_transmissions.pop(active_contact, None)
        bundle.holder = None
        bundle.status = BundleStatus.EXPIRED
        bundle.attempt += 1
        self._record("bundle_expired", bundle_id=bundle_id)
        self._wake_queued_bundles(except_bundle=bundle_id)

    def _schedule_route(self, bundle_id: str, at_us: int) -> None:
        if at_us not in self._dispatch_scheduled:
            self._dispatch_scheduled.add(at_us)
            self._schedule(at_us, EventPriority.ROUTE, "dispatch")

    def _handle_dispatch(self) -> None:
        queued = sorted(
            (
                (bundle.queued_at_us if bundle.queued_at_us is not None else self._time_us, bundle_id)
                for bundle_id, bundle in self._bundles.items()
                if bundle.status == BundleStatus.QUEUED and bundle.holder is not None
            ),
            key=lambda item: (item[0], item[1]),
        )
        for _, bundle_id in queued:
            self._route_bundle(bundle_id)

    def _route_bundle(self, bundle_id: str) -> None:
        bundle = self._bundles.get(bundle_id)
        if bundle is None or bundle.status != BundleStatus.QUEUED or bundle.holder is None:
            return
        path = self._routing_policy.find_path(
            source=bundle.holder,
            destination=bundle.request.destination,
            start_time_us=self._time_us,
            payload_bytes=bundle.request.payload_bytes,
            contacts=self._routing_contacts(),
            forbidden_nodes=bundle.visited - {bundle.holder},
        )
        if not path:
            return
        contact = path[0]
        tx_start = max(self._time_us, contact.start_us)
        if tx_start > self._time_us:
            self._schedule_route(bundle_id, tx_start)
            return
        busy_bundle = self._active_by_contact.get(contact.contact_id)
        if busy_bundle is not None:
            completion = next(
                (
                    event.time_us
                    for event in self._queue
                    if event.kind == "transmission_complete"
                    and event.contact_id == contact.contact_id
                ),
                None,
            )
            if completion is not None:
                self._schedule_route(bundle_id, completion)
            return

        duration = serialization_duration_us(
            bundle.request.payload_bytes, contact.rate_bits_per_second
        )
        if tx_start + duration >= contact.end_us:
            return
        bundle.status = BundleStatus.TRANSMITTING
        bundle.attempt += 1
        self._active_by_contact[contact.contact_id] = bundle_id
        self._active_transmissions[contact.contact_id] = ActiveTransmissionSnapshot(
            bundle_id=bundle_id,
            contact_id=contact.contact_id,
            from_node=contact.from_node,
            to_node=contact.to_node,
            start_time_us=tx_start,
            serialization_complete_us=tx_start + duration,
        )
        self._record(
            "transmission_started",
            bundle_id=bundle_id,
            node_id=bundle.holder,
            contact_id=contact.contact_id,
            details=(("duration_us", str(duration)),),
        )
        self._schedule(
            tx_start + duration,
            EventPriority.TRANSMISSION_COMPLETE,
            "transmission_complete",
            bundle_id=bundle_id,
            contact_id=contact.contact_id,
            attempt=bundle.attempt,
        )

    def _handle_transmission_complete(self, event: _ScheduledEvent) -> None:
        bundle = self._bundles.get(event.bundle_id or "")
        contact = self._contacts_by_id.get(event.contact_id or "")
        if (
            bundle is None
            or contact is None
            or bundle.status != BundleStatus.TRANSMITTING
            or bundle.attempt != event.attempt
            or self._active_by_contact.get(contact.contact_id) != bundle.request.bundle_id
        ):
            return
        if self._time_us >= bundle.expiry_time_us:
            self._handle_expiration(bundle.request.bundle_id)
            return
        del self._active_by_contact[contact.contact_id]
        self._active_transmissions.pop(contact.contact_id, None)
        bundle.status = BundleStatus.IN_TRANSIT
        self._record(
            "transmission_completed",
            bundle_id=bundle.request.bundle_id,
            node_id=contact.from_node,
            contact_id=contact.contact_id,
        )
        self._schedule(
            self._time_us + contact.propagation_delay_us,
            EventPriority.RECEIVER_ARRIVAL,
            "receiver_arrival",
            bundle_id=bundle.request.bundle_id,
            contact_id=contact.contact_id,
            attempt=event.attempt,
        )
        self._wake_queued_bundles(except_bundle=bundle.request.bundle_id)

    def _routing_contacts(self) -> tuple[Contact, ...]:
        result = []
        for contact in self._contacts:
            cutoff = self._contact_cutoffs.get(contact.contact_id)
            if cutoff is None:
                result.append(contact)
            elif contact.start_us < cutoff:
                result.append(replace(contact, end_us=cutoff))
        return tuple(result)

    def _handle_contact_interruption(self, contact_id: str | None) -> None:
        if contact_id is None:
            return
        self._contact_cutoffs[contact_id] = self._time_us
        transmission = self._active_transmissions.pop(contact_id, None)
        bundle_id = self._active_by_contact.pop(contact_id, None)
        self._record("contact_interrupted", contact_id=contact_id)
        if bundle_id is None or transmission is None:
            return
        bundle = self._bundles[bundle_id]
        if bundle.status != BundleStatus.TRANSMITTING:
            return
        contact = self._contacts_by_id[contact_id]
        elapsed_us = max(0, self._time_us - transmission.start_time_us)
        partial_bits = min(
            bundle.request.payload_bytes * 8,
            elapsed_us * contact.rate_bits_per_second // 1_000_000,
        )
        bundle.status = BundleStatus.QUEUED
        bundle.attempt += 1
        self._record(
            "transmission_interrupted",
            bundle_id=bundle_id,
            node_id=bundle.holder,
            contact_id=contact_id,
            details=(("discarded_partial_bits", str(partial_bits)),),
        )
        self._schedule_route(bundle_id, self._time_us)
        self._wake_queued_bundles(except_bundle=bundle_id)

    def _handle_receiver_arrival(self, event: _ScheduledEvent) -> None:
        bundle = self._bundles.get(event.bundle_id or "")
        contact = self._contacts_by_id.get(event.contact_id or "")
        if bundle is None or contact is None or bundle.status != BundleStatus.IN_TRANSIT:
            return
        if bundle.attempt != event.attempt:
            return
        if self._time_us >= bundle.expiry_time_us:
            self._handle_expiration(bundle.request.bundle_id)
            return
        receiver = contact.to_node
        if receiver in bundle.visited:
            self._record("duplicate_or_loop_rejected", bundle_id=bundle.request.bundle_id, node_id=receiver)
            bundle.status = BundleStatus.QUEUED
            self._schedule_route(bundle.request.bundle_id, self._time_us)
            return
        if self._occupancy[receiver] + bundle.request.payload_bytes > self._nodes[receiver].buffer_capacity_bytes:
            self._record("receiver_buffer_rejected", bundle_id=bundle.request.bundle_id, node_id=receiver)
            bundle.status = BundleStatus.QUEUED
            self._schedule_route(bundle.request.bundle_id, self._time_us)
            return

        sender = bundle.holder
        assert sender is not None
        self._change_occupancy(sender, -bundle.request.payload_bytes)
        self._change_occupancy(receiver, bundle.request.payload_bytes)
        bundle.holder = receiver
        bundle.visited.add(receiver)
        bundle.history.append(
            ForwardingRecord(
                from_node=contact.from_node,
                to_node=receiver,
                contact_id=contact.contact_id,
                transmission_start_us=event.time_us
                - contact.propagation_delay_us
                - serialization_duration_us(
                    bundle.request.payload_bytes, contact.rate_bits_per_second
                ),
                serialization_complete_us=event.time_us - contact.propagation_delay_us,
                receiver_acceptance_us=event.time_us,
                from_position_km=position_and_velocity_ecef(
                    self._nodes[contact.from_node],
                    event.time_us - contact.propagation_delay_us - serialization_duration_us(
                        bundle.request.payload_bytes, contact.rate_bits_per_second
                    ),
                )[0],
                to_position_km=position_and_velocity_ecef(
                    self._nodes[receiver], event.time_us - contact.propagation_delay_us
                )[0],
            )
        )
        if receiver == bundle.request.destination:
            bundle.status = BundleStatus.DELIVERED
            self._record("bundle_delivered", bundle_id=bundle.request.bundle_id, node_id=receiver, contact_id=contact.contact_id)
            bundle.holder = None
            self._change_occupancy(receiver, -bundle.request.payload_bytes)
        else:
            bundle.status = BundleStatus.QUEUED
            bundle.queued_at_us = self._time_us
            self._record("bundle_queued", bundle_id=bundle.request.bundle_id, node_id=receiver, contact_id=contact.contact_id)
            self._schedule_route(bundle.request.bundle_id, self._time_us)
        self._wake_queued_bundles(except_bundle=bundle.request.bundle_id)

    def _handle_contact_end(self, contact_id: str | None, event_time_us: int) -> None:
        if contact_id is None:
            return
        contact = self._contacts_by_id.get(contact_id)
        if contact is None or contact.end_us != event_time_us:
            return
        bundle_id = self._active_by_contact.pop(contact_id, None)
        self._active_transmissions.pop(contact_id, None)
        self._record("contact_ended", contact_id=contact_id)
        if bundle_id is None:
            return
        bundle = self._bundles[bundle_id]
        if bundle.status == BundleStatus.TRANSMITTING:
            bundle.status = BundleStatus.QUEUED
            bundle.attempt += 1
            self._record("transmission_interrupted", bundle_id=bundle_id, contact_id=contact_id)
            self._schedule_route(bundle_id, self._time_us)
            self._wake_queued_bundles(except_bundle=bundle_id)

    def _wake_queued_bundles(self, *, except_bundle: str) -> None:
        for bundle_id, bundle in sorted(self._bundles.items()):
            if bundle_id != except_bundle and bundle.status == BundleStatus.QUEUED:
                self._schedule_route(bundle_id, self._time_us)

    def _change_occupancy(self, node_id: str, delta_bytes: int) -> None:
        next_occupancy = self._occupancy[node_id] + delta_bytes
        if next_occupancy < 0:
            raise RuntimeError(f"buffer occupancy underflow for node {node_id}")
        self._occupancy[node_id] = next_occupancy
        self._buffer_samples.append(
            BufferSample(
                time_us=self._time_us,
                node_id=node_id,
                occupancy_bytes=next_occupancy,
            )
        )

    def snapshot(self) -> SimulationSnapshot:
        nodes = tuple(
            NodeSnapshot(
                node=self._nodes[node_id],
                buffer_occupancy_bytes=self._occupancy[node_id],
                position_km=position_and_velocity_ecef(self._nodes[node_id], self._time_us)[0],
                velocity_km_s=position_and_velocity_ecef(self._nodes[node_id], self._time_us)[1],
            )
            for node_id in sorted(self._nodes)
        )
        bundles = tuple(
            BundleSnapshot(
                bundle_id=bundle_id,
                source=bundle.request.source,
                destination=bundle.request.destination,
                payload_bytes=bundle.request.payload_bytes,
                creation_time_us=bundle.request.creation_time_us,
                expiry_time_us=bundle.expiry_time_us,
                holder=bundle.holder,
                status=bundle.status,
                forwarding_history=tuple(bundle.history),
            )
            for bundle_id, bundle in sorted(self._bundles.items())
        )
        return SimulationSnapshot(
            time_us=self._time_us,
            routing_policy=self._routing_policy.name,
            nodes=nodes,
            contacts=self._contacts,
            bundles=bundles,
            active_transmissions=tuple(
                self._active_transmissions[contact_id]
                for contact_id in sorted(self._active_transmissions)
            ),
            buffer_samples=tuple(self._buffer_samples),
            events=tuple(self._records),
        )
