"""Deterministic, contact-aware discrete-event simulation engine."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from enum import IntEnum

from .model import (
    ActiveTransmissionSnapshot,
    BundleRequest,
    BundleSnapshot,
    BundleStatus,
    Contact,
    EventRecord,
    ForwardingRecord,
    Node,
    NodeSnapshot,
    SimulationSnapshot,
)
from .routing import earliest_arrival_path, serialization_duration_us


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
    history: list[ForwardingRecord] = field(default_factory=list)
    visited: set[str] = field(default_factory=set)
    attempt: int = 0


class SimulationEngine:
    """Owns all mutable state for one deterministic simulation run."""

    def __init__(self, *, nodes: tuple[Node, ...], contacts: tuple[Contact, ...]) -> None:
        self._nodes = self._validate_nodes(nodes)
        self._contacts = self._validate_contacts(contacts, self._nodes)
        self._contacts_by_id = {contact.contact_id: contact for contact in self._contacts}
        self._occupancy = {node_id: 0 for node_id in self._nodes}
        self._bundles: dict[str, _Bundle] = {}
        self._requests: dict[str, BundleRequest] = {}
        self._active_by_contact: dict[str, str] = {}
        self._active_transmissions: dict[str, ActiveTransmissionSnapshot] = {}
        self._queue: list[_ScheduledEvent] = []
        self._queue_sequence = 0
        self._record_sequence = 0
        self._time_us = 0
        self._records: list[EventRecord] = []
        self._route_scheduled: set[tuple[str, int]] = set()

        for contact in self._contacts:
            self._schedule(contact.start_us, EventPriority.CONTACT_START, "contact_start", contact_id=contact.contact_id)
            self._schedule(contact.end_us, EventPriority.CONTACT_END, "contact_end", contact_id=contact.contact_id)

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
                    not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in node.position_km
                )
            ):
                raise ValueError(f"node {node.node_id} position must contain three coordinates")
            by_id[node.node_id] = node
        if not by_id:
            raise ValueError("at least one node is required")
        return by_id

    @staticmethod
    def _validate_contacts(
        contacts: tuple[Contact, ...], nodes: dict[str, Node]
    ) -> tuple[Contact, ...]:
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
            timestamps = (contact.start_us, contact.end_us, contact.propagation_delay_us)
            if any(not isinstance(value, int) or isinstance(value, bool) for value in timestamps):
                raise ValueError(f"contact {contact.contact_id} timestamps must be integer microseconds")
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

    def add_bundle(self, request: BundleRequest) -> None:
        """Schedule one bundle generation attempt without mutating state immediately."""
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
        previous_record_count = len(self._records)
        self._process(event)
        if event.kind == "route" and event.bundle_id is not None:
            self._route_scheduled.discard((event.bundle_id, event.time_us))
        return self._records[-1] if len(self._records) > previous_record_count else None

    def run_until(self, horizon_us: int) -> SimulationSnapshot:
        if horizon_us < self._time_us:
            raise ValueError("simulation horizon cannot be in the past")
        while self._queue and self._queue[0].time_us <= horizon_us:
            self.step()
        self._time_us = horizon_us
        return self.snapshot()

    def run_to_completion(self) -> SimulationSnapshot:
        while self._queue:
            self.step()
        return self.snapshot()

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
            self._handle_contact_end(event.contact_id)
        elif event.kind == "bundle_generation":
            self._handle_generation(event.bundle_id)
        elif event.kind == "bundle_expiration":
            self._handle_expiration(event.bundle_id)
        elif event.kind == "route":
            self._handle_route(event.bundle_id)
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
        if self._occupancy[request.source] + request.payload_bytes > source.buffer_capacity_bytes:
            self._record("bundle_rejected_at_source", bundle_id=bundle_id, node_id=request.source)
            return
        bundle = self._bundles[bundle_id]
        bundle.status = BundleStatus.QUEUED
        bundle.holder = request.source
        bundle.visited.add(request.source)
        self._occupancy[request.source] += request.payload_bytes
        self._record("bundle_queued", bundle_id=bundle_id, node_id=request.source)
        self._schedule_route(bundle_id, self._time_us)

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
            self._occupancy[bundle.holder] -= bundle.request.payload_bytes
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

    def _schedule_route(self, bundle_id: str, at_us: int) -> None:
        key = (bundle_id, at_us)
        if key not in self._route_scheduled:
            self._route_scheduled.add(key)
            self._schedule(at_us, EventPriority.ROUTE, "route", bundle_id=bundle_id)

    def _handle_route(self, bundle_id: str | None) -> None:
        if bundle_id is None:
            return
        bundle = self._bundles.get(bundle_id)
        if bundle is None or bundle.status != BundleStatus.QUEUED or bundle.holder is None:
            return
        path = earliest_arrival_path(
            source=bundle.holder,
            destination=bundle.request.destination,
            start_time_us=self._time_us,
            payload_bytes=bundle.request.payload_bytes,
            contacts=self._contacts,
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
        self._occupancy[sender] -= bundle.request.payload_bytes
        self._occupancy[receiver] += bundle.request.payload_bytes
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
            )
        )
        if receiver == bundle.request.destination:
            bundle.status = BundleStatus.DELIVERED
            self._record("bundle_delivered", bundle_id=bundle.request.bundle_id, node_id=receiver, contact_id=contact.contact_id)
            bundle.holder = None
            self._occupancy[receiver] -= bundle.request.payload_bytes
        else:
            bundle.status = BundleStatus.QUEUED
            self._record("bundle_queued", bundle_id=bundle.request.bundle_id, node_id=receiver, contact_id=contact.contact_id)
            self._schedule_route(bundle.request.bundle_id, self._time_us)

    def _handle_contact_end(self, contact_id: str | None) -> None:
        if contact_id is None:
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

    def _wake_queued_bundles(self, *, except_bundle: str) -> None:
        for bundle_id, bundle in sorted(self._bundles.items()):
            if bundle_id != except_bundle and bundle.status == BundleStatus.QUEUED:
                self._schedule_route(bundle_id, self._time_us)

    def snapshot(self) -> SimulationSnapshot:
        nodes = tuple(
            NodeSnapshot(node=self._nodes[node_id], buffer_occupancy_bytes=self._occupancy[node_id])
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
            nodes=nodes,
            contacts=self._contacts,
            bundles=bundles,
            active_transmissions=tuple(
                self._active_transmissions[contact_id]
                for contact_id in sorted(self._active_transmissions)
            ),
            events=tuple(self._records),
        )
