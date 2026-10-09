export type NodeKind = "satellite" | "ground_station";
export type BundleStatus = "queued" | "transmitting" | "in_transit" | "delivered" | "expired" | "rejected_at_source";
export type RunStatus = "ready" | "running" | "paused" | "completed" | "failed";
export type RoutingPolicy = "contact_aware_earliest_arrival" | "static_minimum_hop";

export interface NodeConfig {
  node_id: string;
  kind: NodeKind;
  buffer_capacity_bytes: number;
  position_km: [number, number, number] | null;
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
  interruptions: { contact_id: string; time_us: number }[];
}

export interface ForwardingRecord {
  from_node: string;
  to_node: string;
  contact_id: string;
  transmission_start_us: number;
  serialization_complete_us: number;
  receiver_acceptance_us: number;
}

export interface NodeState extends NodeConfig {
  buffer_occupancy_bytes: number;
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
  random_seed: number;
  routing_policy: RoutingPolicy;
  node_count: number;
  contact_count: number;
  bundle_count: number;
  normalized_configuration: SimulationConfig;
}

export interface Metrics {
  generated_count: number;
  delivered_count: number;
  undelivered_count: number;
  expired_count: number;
  delivery_ratio: number | null;
  mean_delivery_latency_us: number | null;
  mean_hop_count: number | null;
  contact_utilization_fraction: number | null;
  peak_total_buffer_occupancy_bytes: number;
}
