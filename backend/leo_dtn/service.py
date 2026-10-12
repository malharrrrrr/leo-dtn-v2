"""In-memory run control that adapts REST commands to the simulation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from .api_models import (
    BundleInput,
    ContactInput,
    ContactInterruptionInput,
    CreateSimulationRequest,
    NodeInput,
    SimulationConfigurationInput,
)
from .engine import SimulationEngine
from .model import BundleRequest, Contact, ContactInterruption, Node
from .orbit import generate_contact_plan
from .routing import ContactAwareEarliestArrival, RoutingPolicy, StaticMinimumHop


ROUTING_POLICIES: dict[str, type[RoutingPolicy]] = {
    ContactAwareEarliestArrival.name: ContactAwareEarliestArrival,
    StaticMinimumHop.name: StaticMinimumHop,
}
CONTACT_PLAN_LOOKAHEAD_US = 120 * 1_000_000
CONTACT_PLAN_EXTENSION_US = 3_600 * 1_000_000


class InvalidRunTransition(Exception):
    pass


@dataclass(slots=True)
class SimulationSession:
    simulation_id: str
    configuration: SimulationConfigurationInput
    random_seed: int
    horizon_us: int
    routing_policy_name: str
    status: str = "ready"
    playback_speed: float = 1.0
    engine: SimulationEngine = field(init=False)
    initial_horizon_us: int = field(init=False)
    lock: RLock = field(default_factory=RLock, repr=False)

    def __post_init__(self) -> None:
        if self.configuration.orbital_contact_generation:
            self.horizon_us = max(
                self.horizon_us,
                max(
                    (bundle.creation_time_us + bundle.ttl_us for bundle in self.configuration.bundles),
                    default=0,
                ),
            )
        self.initial_horizon_us = self.horizon_us
        self.engine = self._new_engine()

    def _new_engine(self) -> SimulationEngine:
        try:
            policy_type = ROUTING_POLICIES[self.routing_policy_name]
        except KeyError as exc:
            raise ValueError(f"unknown routing policy: {self.routing_policy_name}") from exc
        nodes = tuple(_node_to_domain(node) for node in self.configuration.nodes)
        contacts = tuple(_contact_to_domain(contact) for contact in self.configuration.contacts)
        if self.configuration.orbital_contact_generation:
            contacts += generate_contact_plan(
                nodes,
                horizon_us=self.horizon_us,
                sample_interval_us=self.configuration.contact_sample_interval_us,
                rate_bits_per_second=self.configuration.orbital_link_rate_bits_per_second,
                minimum_elevation_deg=self.configuration.minimum_elevation_deg,
            )
        return SimulationEngine(
            nodes=nodes,
            contacts=contacts,
            interruptions=tuple(
                _interruption_to_domain(item) for item in self.configuration.interruptions
            ),
            routing_policy=policy_type(),
        )

    def initialize_bundles(self) -> None:
        for bundle in self.configuration.bundles:
            request = _bundle_to_domain(bundle)
            interval = self.configuration.bundle_generation_interval_us
            if interval is None:
                self.engine.add_bundle(request)
            else:
                self.engine.add_recurring_bundle(request, interval_us=interval)

    def start(self) -> None:
        with self.lock:
            if self.status != "ready":
                raise InvalidRunTransition("only a ready simulation can be started")
            self.status = "running"

    def pause(self) -> None:
        with self.lock:
            if self.status != "running":
                raise InvalidRunTransition("only a running simulation can be paused")
            self.status = "paused"

    def resume(self) -> None:
        with self.lock:
            if self.status != "paused":
                raise InvalidRunTransition("only a paused simulation can be resumed")
            self.status = "running"

    def set_playback_speed(self, speed: float) -> None:
        if speed not in (0.25, 0.5, 1.0, 2.0, 4.0):
            raise ValueError("playback speed must be one of 0.25, 0.5, 1, 2, or 4")
        with self.lock:
            self.playback_speed = speed

    def step(self) -> int:
        with self.lock:
            if self.status not in ("ready", "paused"):
                raise InvalidRunTransition("step requires a ready or paused simulation")
            if self.configuration.orbital_contact_generation:
                next_time = self.engine.next_event_time_us
                target = min(next_time if next_time is not None else self.horizon_us, self.horizon_us)
                self._ensure_contact_plan(target)
            elif self._next_event_is_past_horizon():
                self.engine.run_until(self.horizon_us, max_events=0)
                self.status = "completed"
                return 0
            before = self.engine.events_processed
            self.engine.step()
            processed = self.engine.events_processed - before
            if not self.configuration.orbital_contact_generation and self._next_event_is_past_horizon():
                self.engine.run_until(self.horizon_us, max_events=0)
                self.status = "completed"
            else:
                self.status = "paused"
            return processed

    def advance(self, *, target_time_us: int, max_events: int) -> tuple[int, bool]:
        with self.lock:
            if self.status != "running":
                raise InvalidRunTransition("advance requires a running simulation")
            if target_time_us < self.engine.time_us:
                raise ValueError("target time cannot be before the current simulated time")
            if self.configuration.orbital_contact_generation:
                self._ensure_contact_plan(target_time_us)
            elif target_time_us > self.horizon_us:
                raise ValueError("target time must be between current simulated time and horizon")
            before = self.engine.events_processed
            self.engine.run_until(target_time_us, max_events=max_events)
            processed = self.engine.events_processed - before
            reached_target = (
                self.engine.time_us == target_time_us
                and (
                    self.engine.next_event_time_us is None
                    or self.engine.next_event_time_us > target_time_us
                )
            )
            if not self.configuration.orbital_contact_generation and reached_target and target_time_us == self.horizon_us:
                self.status = "completed"
            return processed, reached_target

    def reset(self) -> None:
        with self.lock:
            self.horizon_us = self.initial_horizon_us
            self.playback_speed = 1.0
            self.engine = self._new_engine()
            self.initialize_bundles()
            self.status = "ready"

    def _ensure_contact_plan(self, target_time_us: int) -> None:
        """Keep enough future contacts for a bundle to route before its TTL."""
        max_bundle_ttl_us = max(
            (bundle.ttl_us for bundle in self.configuration.bundles),
            default=0,
        )
        required_horizon_us = max(
            target_time_us + CONTACT_PLAN_LOOKAHEAD_US,
            target_time_us + max_bundle_ttl_us,
        )
        if required_horizon_us <= self.horizon_us:
            return
        self.horizon_us = max(
            self.horizon_us + CONTACT_PLAN_EXTENSION_US,
            required_horizon_us,
        )
        nodes = tuple(_node_to_domain(node) for node in self.configuration.nodes)
        generated = generate_contact_plan(
            nodes,
            horizon_us=self.horizon_us,
            sample_interval_us=self.configuration.contact_sample_interval_us,
            rate_bits_per_second=self.configuration.orbital_link_rate_bits_per_second,
            minimum_elevation_deg=self.configuration.minimum_elevation_deg,
        )
        self.engine.extend_contact_plan(generated)

    def _next_event_is_past_horizon(self) -> bool:
        next_time = self.engine.next_event_time_us
        return next_time is None or next_time > self.horizon_us


class SimulationManager:
    """Owns in-memory sessions for one local API process."""

    def __init__(self) -> None:
        self._sessions: dict[str, SimulationSession] = {}
        self._next_id = 1
        self._lock = RLock()

    def create(self, request: CreateSimulationRequest) -> SimulationSession:
        configuration = request.configuration or default_scenario(request.scenario_id or "")
        with self._lock:
            simulation_id = f"sim-{self._next_id:06d}"
            self._next_id += 1
            session = SimulationSession(
                simulation_id=simulation_id,
                configuration=configuration,
                random_seed=request.random_seed,
                horizon_us=request.horizon_us,
                routing_policy_name=request.routing_policy,
            )
            session.initialize_bundles()
            self._sessions[simulation_id] = session
            return session

    def get(self, simulation_id: str) -> SimulationSession:
        with self._lock:
            session = self._sessions.get(simulation_id)
        if session is None:
            raise KeyError(simulation_id)
        return session


def default_scenario(scenario_id: str) -> SimulationConfigurationInput:
    from .scenarios import scenario_definition

    definition = scenario_definition(scenario_id)
    if definition is None:
        raise KeyError(scenario_id)
    return SimulationConfigurationInput(
        nodes=tuple(
            NodeInput(
                node_id=item.node_id,
                kind=item.kind,
                buffer_capacity_bytes=item.buffer_capacity_bytes,
                position_km=item.position_km,
                orbit=item.orbit,
            )
            for item in definition.nodes
        ),
        contacts=tuple(
            ContactInput(
                contact_id=item.contact_id,
                from_node=item.from_node,
                to_node=item.to_node,
                start_us=item.start_us,
                end_us=item.end_us,
                rate_bits_per_second=item.rate_bits_per_second,
                propagation_delay_us=item.propagation_delay_us,
            )
            for item in definition.contacts
        ),
        bundles=tuple(
            BundleInput(
                bundle_id=item.bundle_id,
                source=item.source,
                destination=item.destination,
                payload_bytes=item.payload_bytes,
                creation_time_us=item.creation_time_us,
                ttl_us=item.ttl_us,
            )
            for item in definition.bundles
        ),
        orbital_contact_generation=definition.orbital_contact_generation,
        contact_sample_interval_us=definition.contact_sample_interval_us,
        minimum_elevation_deg=definition.minimum_elevation_deg,
        orbital_link_rate_bits_per_second=definition.orbital_link_rate_bits_per_second,
        bundle_generation_interval_us=definition.bundle_generation_interval_us,
    )


def _node_to_domain(value: NodeInput) -> Node:
    return Node(value.node_id, value.kind, value.buffer_capacity_bytes, value.position_km, value.orbit)


def _contact_to_domain(value: ContactInput) -> Contact:
    return Contact(
        value.contact_id,
        value.from_node,
        value.to_node,
        value.start_us,
        value.end_us,
        value.rate_bits_per_second,
        value.propagation_delay_us,
    )


def _bundle_to_domain(value: BundleInput) -> BundleRequest:
    return BundleRequest(
        value.bundle_id,
        value.source,
        value.destination,
        value.payload_bytes,
        value.creation_time_us,
        value.ttl_us,
    )


def _interruption_to_domain(value: ContactInterruptionInput) -> ContactInterruption:
    return ContactInterruption(value.contact_id, value.time_us)
