export type NodeKind = "satellite" | "ground_station";
export type BundleStatus = "queued" | "transmitting" | "in_transit" | "delivered" | "expired" | "rejected_at_source";
export type RunStatus = "ready" | "running" | "paused" | "completed" | "failed";
export type RoutingPolicy = "contact_aware_earliest_arrival" | "static_minimum_hop";
export type PlaybackSpeed = 0.25 | 0.5 | 1 | 2 | 4;

export interface NodeConfig {
  node_id: string;
  kind: NodeKind;
  buffer_capacity_bytes: number;
  position_km: [number, number, number] | null;
  velocity_km_s?: [number, number, number] | null;
  orbit?: { altitude_km: number; inclination_deg: number; raan_deg: number; phase_deg: number } | null;
}

export interface ContactConfig {
  contact_id: string;
  from_node: string;
  to_node: string;
  start_us: number;
  end_us: number;
  rate_bits_per_second: number;
  propagation_delay_us: number;
}

export interface BundleConfig {
  bundle_id: string;
  source: string;
  destination: string;
  payload_bytes: number;
  creation_time_us: number;
  ttl_us: number;
}

export interface SimulationConfig {
  nodes: NodeConfig[];
  contacts: ContactConfig[];
  bundles: BundleConfig[];
  bundle_generation_interval_us?: number | null;
  interruptions: { contact_id: string; time_us: number }[];
  orbital_contact_generation?: boolean;
  contact_sample_interval_us?: number;
  minimum_elevation_deg?: number;
  orbital_link_rate_bits_per_second?: number;
}

export interface ScenarioSummary {
  scenario_id: string;
  name: string;
  description: string;
  focus: string;
  node_count: number;
  satellite_count: number;
  ground_station_count: number;
  contact_count: number;
  bundle_count: number;
  orbital_contact_generation: boolean;
}

export interface ScenarioDetails extends ScenarioSummary {
  configuration: SimulationConfig;
}

export interface ForwardingRecord {
  from_node: string;
  to_node: string;
  contact_id: string;
  transmission_start_us: number;
  serialization_complete_us: number;
  receiver_acceptance_us: number;
  from_position_km: [number, number, number] | null;
  to_position_km: [number, number, number] | null;
}

export interface NodeState extends NodeConfig {
  buffer_occupancy_bytes: number;
  position_km: [number, number, number] | null;
  velocity_km_s: [number, number, number] | null;
}

export interface ContactState extends ContactConfig {
  status: "planned" | "active" | "interrupted" | "completed";
}

export interface BundleState extends BundleConfig {
  expiry_time_us: number;
  holder: string | null;
  status: BundleStatus;
  forwarding_history: ForwardingRecord[];
}

export interface SimulationEvent {
  sequence: number;
  time_us: number;
  kind: string;
  bundle_id: string | null;
  node_id: string | null;
  contact_id: string | null;
  details: Record<string, string>;
}

export interface ActiveTransmission {
  bundle_id: string;
  contact_id: string;
  from_node: string;
  to_node: string;
  start_time_us: number;
  serialization_complete_us: number;
}

export interface SimulationSnapshot {
  simulation_id: string;
  status: RunStatus;
  time_us: number;
  horizon_us: number;
  playback_speed: PlaybackSpeed;
  routing_policy: RoutingPolicy;
  nodes: NodeState[];
  contacts: ContactState[];
  bundles: BundleState[];
  active_transmissions: ActiveTransmission[];
  events: SimulationEvent[];
}

export interface CreatedSimulation {
  simulation_id: string;
  status: RunStatus;
  simulated_time_us: number;
  horizon_us: number;
  playback_speed: PlaybackSpeed;
  random_seed: number;
  routing_policy: RoutingPolicy;
  node_count: number;
  contact_count: number;
  bundle_count: number;
  normalized_configuration: SimulationConfig;
}

export interface Metrics {
  horizon_us: number;
  generated_count: number;
  delivered_count: number;
  undelivered_count: number;
  source_rejected_count: number;
  expired_count: number;
  delivery_ratio: number | null;
  expiration_ratio: number | null;
  mean_delivery_latency_us: number | null;
  median_delivery_latency_us: number | null;
  mean_hop_count: number | null;
  median_hop_count: number | null;
  contact_utilization_fraction: number | null;
  mean_total_buffer_occupancy_bytes: number;
  peak_total_buffer_occupancy_bytes: number;
  mean_total_buffer_capacity_fraction: number | null;
  status_counts: [string, number][];
  per_node_buffer: { node_id: string; peak_occupancy_bytes: number; mean_occupancy_bytes: number; mean_capacity_fraction: number | null }[];
  per_contact_utilization: { contact_id: string; transmitted_payload_bits: number; scheduled_capacity_bits: number; utilization_fraction: number | null }[];
}

export interface PolicyComparison {
  routing_policy: RoutingPolicy;
  metrics: Metrics;
}

export interface ScenarioComparison {
  scenario: ScenarioDetails;
  results: PolicyComparison[];
}

export interface ExperimentComparison {
  random_seed: number;
  horizon_us: number;
  scenarios: ScenarioComparison[];
}
