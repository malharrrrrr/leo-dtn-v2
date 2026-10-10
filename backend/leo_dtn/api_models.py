"""Pydantic request and response models for the local REST adapter."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .model import BundleStatus, CircularOrbit, NodeKind


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeInput(APIModel):
    node_id: str = Field(min_length=1)
    kind: NodeKind
    buffer_capacity_bytes: int = Field(ge=0)
    position_km: tuple[float, float, float] | None = None
    orbit: CircularOrbit | None = None

    @model_validator(mode="after")
    def validate_orbit(self) -> NodeInput:
        if self.orbit is not None:
            if self.kind != NodeKind.SATELLITE:
                raise ValueError("only satellites may have orbital elements")
            if not 100 <= self.orbit.altitude_km <= 2_000:
                raise ValueError("circular orbit altitude must be between 100 and 2,000 km")
            if not 0 <= self.orbit.inclination_deg <= 180:
                raise ValueError("inclination must be between 0 and 180 degrees")
        return self


class ContactInput(APIModel):
    contact_id: str = Field(min_length=1)
    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    start_us: int = Field(ge=0)
    end_us: int = Field(gt=0)
    rate_bits_per_second: int = Field(gt=0)
    propagation_delay_us: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check_window(self) -> ContactInput:
        if self.start_us >= self.end_us:
            raise ValueError("contact start_us must be less than end_us")
        return self


class BundleInput(APIModel):
    bundle_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    payload_bytes: int = Field(gt=0)
    creation_time_us: int = Field(ge=0)
    ttl_us: int = Field(gt=0)


class ContactInterruptionInput(APIModel):
    contact_id: str = Field(min_length=1)
    time_us: int = Field(ge=0)


class SimulationConfigurationInput(APIModel):
    nodes: tuple[NodeInput, ...] = Field(min_length=1)
    contacts: tuple[ContactInput, ...] = ()
    bundles: tuple[BundleInput, ...] = ()
    bundle_generation_interval_us: int | None = Field(default=None, gt=0)
    interruptions: tuple[ContactInterruptionInput, ...] = ()
    orbital_contact_generation: bool = False
    contact_sample_interval_us: int = Field(default=10_000_000, ge=100_000, le=300_000_000)
    minimum_elevation_deg: float = Field(default=10.0, ge=0.0, le=45.0)
    orbital_link_rate_bits_per_second: int = Field(default=100_000_000, gt=0)


RoutingPolicyName = Literal["contact_aware_earliest_arrival", "static_minimum_hop"]


class CreateSimulationRequest(APIModel):
    scenario_id: str | None = None
    configuration: SimulationConfigurationInput | None = None
    random_seed: int
    horizon_us: int = Field(gt=0)
    routing_policy: RoutingPolicyName = "contact_aware_earliest_arrival"

    @model_validator(mode="after")
    def require_one_configuration_source(self) -> CreateSimulationRequest:
        if (self.scenario_id is None) == (self.configuration is None):
            raise ValueError("provide exactly one of scenario_id or configuration")
        if self.scenario_id is not None and not self.scenario_id.strip():
            raise ValueError("scenario_id must be non-empty")
        return self


class SimulationStatusResponse(APIModel):
    simulation_id: str
    status: Literal["ready", "running", "paused", "completed", "failed"]
    simulated_time_us: int
    horizon_us: int
    random_seed: int
    routing_policy: str
    node_count: int
    contact_count: int
    bundle_count: int


class RunCreatedResponse(SimulationStatusResponse):
    normalized_configuration: SimulationConfigurationInput


class NodeResponse(APIModel):
    node_id: str
    kind: NodeKind
    buffer_capacity_bytes: int
    buffer_occupancy_bytes: int
    position_km: tuple[float, float, float] | None
    velocity_km_s: tuple[float, float, float] | None = None
    orbit: CircularOrbit | None = None


class ContactResponse(APIModel):
    contact_id: str
    from_node: str
    to_node: str
    start_us: int
    end_us: int
    rate_bits_per_second: int
    propagation_delay_us: int
    status: Literal["planned", "active", "interrupted", "completed"]


class ForwardingResponse(APIModel):
    from_node: str
    to_node: str
    contact_id: str
    transmission_start_us: int
    serialization_complete_us: int
    receiver_acceptance_us: int
    from_position_km: tuple[float, float, float] | None = None
    to_position_km: tuple[float, float, float] | None = None


class BundleResponse(APIModel):
    bundle_id: str
    source: str
    destination: str
    payload_bytes: int
    creation_time_us: int
    expiry_time_us: int
    holder: str | None
    status: BundleStatus
    forwarding_history: tuple[ForwardingResponse, ...]


class EventResponse(APIModel):
    sequence: int
    time_us: int
    kind: str
    bundle_id: str | None
    node_id: str | None
    contact_id: str | None
    details: dict[str, str]


class ActiveTransmissionResponse(APIModel):
    bundle_id: str
    contact_id: str
    from_node: str
    to_node: str
    start_time_us: int
    serialization_complete_us: int


class SimulationSnapshotResponse(APIModel):
    simulation_id: str
    status: Literal["ready", "running", "paused", "completed", "failed"]
    time_us: int
    horizon_us: int
    routing_policy: str
    nodes: tuple[NodeResponse, ...]
    contacts: tuple[ContactResponse, ...]
    bundles: tuple[BundleResponse, ...]
    active_transmissions: tuple[ActiveTransmissionResponse, ...]
    events: tuple[EventResponse, ...]


class AdvanceRequest(APIModel):
    target_time_us: int | None = Field(default=None, ge=0)
    max_events: int = Field(default=1_000, ge=1, le=10_000)


class AdvanceResponse(APIModel):
    simulation: SimulationSnapshotResponse
    target_time_us: int
    events_processed: int
    reached_target: bool


class ScenarioSummary(APIModel):
    scenario_id: str
    name: str
    description: str


class ScenarioResponse(ScenarioSummary):
    configuration: SimulationConfigurationInput


class NodeMetricsResponse(APIModel):
    node_id: str
    peak_occupancy_bytes: int
    mean_occupancy_bytes: float
    mean_capacity_fraction: float | None


class ContactMetricsResponse(APIModel):
    contact_id: str
    transmitted_payload_bits: int
    scheduled_capacity_bits: float
    utilization_fraction: float | None


class MetricsResponse(APIModel):
    horizon_us: int
    generated_count: int
    delivered_count: int
    undelivered_count: int
    source_rejected_count: int
    expired_count: int
    delivery_ratio: float | None
    expiration_ratio: float | None
    mean_delivery_latency_us: float | None
    median_delivery_latency_us: float | None
    mean_hop_count: float | None
    median_hop_count: float | None
    mean_total_buffer_occupancy_bytes: float
    peak_total_buffer_occupancy_bytes: int
    mean_total_buffer_capacity_fraction: float | None
    contact_utilization_fraction: float | None
    status_counts: tuple[tuple[str, int], ...]
    per_node_buffer: tuple[NodeMetricsResponse, ...]
    per_contact_utilization: tuple[ContactMetricsResponse, ...]


class ExportFormat(APIModel):
    format: Literal["json", "scenario_csv", "events_csv", "metrics_csv"]
