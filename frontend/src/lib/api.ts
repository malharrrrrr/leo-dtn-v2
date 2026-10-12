import type { CreatedSimulation, Metrics, PlaybackSpeed, RoutingPolicy, ScenarioDetails, ScenarioSummary, SimulationConfig, SimulationSnapshot } from "./contracts";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function createSimulation(configuration: SimulationConfig, routingPolicy: RoutingPolicy, seed: number, horizonUs: number) {
  return request<CreatedSimulation>("/simulations", {
    method: "POST",
    body: JSON.stringify({ configuration, routing_policy: routingPolicy, random_seed: seed, horizon_us: horizonUs }),
  });
}

export function getScenarios() {
  return request<ScenarioSummary[]>("/scenarios");
}

export function getScenario(scenarioId: string) {
  return request<ScenarioDetails>(`/scenarios/${encodeURIComponent(scenarioId)}`);
}

export function postControl(id: string, action: "start" | "pause" | "resume" | "step" | "reset") {
  return request<SimulationSnapshot>(`/simulations/${id}/${action}`, { method: "POST" });
}

export function setSimulationPlaybackSpeed(id: string, speed: PlaybackSpeed) {
  return request<SimulationSnapshot>(`/simulations/${id}/playback-speed`, {
    method: "POST",
    body: JSON.stringify({ speed }),
  });
}

export function advanceSimulation(id: string, targetTimeUs: number) {
  return request<{ simulation: SimulationSnapshot; events_processed: number; reached_target: boolean }>(
    `/simulations/${id}/advance`,
    { method: "POST", body: JSON.stringify({ target_time_us: targetTimeUs, max_events: 1_000 }) },
  );
}

export function getSimulation(id: string) {
  return request<SimulationSnapshot>(`/simulations/${id}/snapshot`);
}

export function getMetrics(id: string) {
  return request<Metrics>(`/simulations/${id}/metrics`);
}
