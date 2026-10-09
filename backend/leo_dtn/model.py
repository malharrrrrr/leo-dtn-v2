"""Small immutable inputs and read-only result types for the engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NodeKind(str, Enum):
    SATELLITE = "satellite"
    GROUND_STATION = "ground_station"


class BundleStatus(str, Enum):
    QUEUED = "queued"
    TRANSMITTING = "transmitting"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXPIRED = "expired"
    REJECTED_AT_SOURCE = "rejected_at_source"


@dataclass(frozen=True, slots=True)
class Node:
    node_id: str
    kind: NodeKind
    buffer_capacity_bytes: int
    position_km: tuple[float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class Contact:
    contact_id: str
    from_node: str
    to_node: str
    start_us: int
    end_us: int
    rate_bits_per_second: int
    propagation_delay_us: int = 0


@dataclass(frozen=True, slots=True)
class ContactInterruption:
    contact_id: str
    time_us: int


@dataclass(frozen=True, slots=True)
class BundleRequest:
    bundle_id: str
    source: str
    destination: str
    payload_bytes: int
    creation_time_us: int
    ttl_us: int


@dataclass(frozen=True, slots=True)
class ForwardingRecord:
    from_node: str
    to_node: str
    contact_id: str
    transmission_start_us: int
    serialization_complete_us: int
    receiver_acceptance_us: int


@dataclass(frozen=True, slots=True)
class BundleSnapshot:
    bundle_id: str
    source: str
    destination: str
    payload_bytes: int
    creation_time_us: int
    expiry_time_us: int
    holder: str | None
    status: BundleStatus
    forwarding_history: tuple[ForwardingRecord, ...]


@dataclass(frozen=True, slots=True)
class EventRecord:
    sequence: int
    time_us: int
    kind: str
    bundle_id: str | None = None
    node_id: str | None = None
    contact_id: str | None = None
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    node: Node
    buffer_occupancy_bytes: int


@dataclass(frozen=True, slots=True)
class ActiveTransmissionSnapshot:
    bundle_id: str
    contact_id: str
    from_node: str
    to_node: str
    start_time_us: int
    serialization_complete_us: int


@dataclass(frozen=True, slots=True)
class BufferSample:
    time_us: int
    node_id: str
    occupancy_bytes: int


@dataclass(frozen=True, slots=True)
class SimulationSnapshot:
    time_us: int
    routing_policy: str
    nodes: tuple[NodeSnapshot, ...]
    contacts: tuple[Contact, ...]
    bundles: tuple[BundleSnapshot, ...]
    active_transmissions: tuple[ActiveTransmissionSnapshot, ...]
    buffer_samples: tuple[BufferSample, ...]
    events: tuple[EventRecord, ...]
