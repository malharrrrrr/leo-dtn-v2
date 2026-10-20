"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Activity, AlertCircle, ChevronDown, CircleHelp, Globe2, History, Layers3, Link2, LoaderCircle,
  Pause, Play, Plus, RotateCcw, Satellite, SkipForward, Sparkles, Waypoints,
} from "lucide-react";
import { advanceSimulation, createSimulation, getMetrics, getSimulation, postControl, setSimulationPlaybackSpeed } from "@/lib/api";
import type { BundleConfig, BundleState, ContactConfig, Metrics, NodeConfig, PlaybackSpeed, RoutingPolicy, RunStatus, SimulationConfig, SimulationSnapshot } from "@/lib/contracts";
import { NetworkScene } from "./network-scene";
import { NetworkTopology } from "./network-topology";
import { cloneScenarioConfiguration, ScenarioLibrary } from "./scenario-library";

const EARTH_RADIUS_KM = 6371;
const groundPosition = (latitude: number, longitude: number): [number, number, number] => {
  const lat = latitude * Math.PI / 180; const lon = longitude * Math.PI / 180;
  return [EARTH_RADIUS_KM * Math.cos(lat) * Math.cos(lon), EARTH_RADIUS_KM * Math.cos(lat) * Math.sin(lon), EARTH_RADIUS_KM * Math.sin(lat)];
};
const DEFAULT_ORBITS = [
  [59, 22], [102, 1.6], [0, 53], [45, 0], [90, 37], [135, 90], [180, 143], [225, 196],
];
const INITIAL_CONFIG: SimulationConfig = {
  nodes: [
    { node_id: "GS-MUMBAI", kind: "ground_station", buffer_capacity_bytes: 10_000_000_000, position_km: groundPosition(19.076, 72.878) },
    ...Array.from({ length: 8 }, (_, index) => ({
      node_id: `SAT-${String(index + 1).padStart(2, "0")}`, kind: "satellite" as const,
      buffer_capacity_bytes: 10_000_000_000, position_km: null,
      orbit: { altitude_km: 550, inclination_deg: 53, raan_deg: DEFAULT_ORBITS[index][0], phase_deg: DEFAULT_ORBITS[index][1] },
    })),
    { node_id: "GS-NEW-YORK", kind: "ground_station", buffer_capacity_bytes: 10_000_000_000, position_km: groundPosition(40.7128, -74.006) },
  ],
  contacts: [],
  bundles: [
    { bundle_id: "BND-001", source: "GS-MUMBAI", destination: "GS-NEW-YORK", payload_bytes: 50_000_000, creation_time_us: 2_000_000, ttl_us: 21_600_000_000 },
  ],
  bundle_generation_interval_us: 60_000_000,
  interruptions: [],
  orbital_contact_generation: true,
  contact_sample_interval_us: 10_000_000,
  minimum_elevation_deg: 10,
  orbital_link_rate_bits_per_second: 100_000_000,
};

const seconds = (us: number) => `${(us / 1_000_000).toFixed(2)} s`;
const bytes = (value: number) => value >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)} MB` : `${value.toLocaleString()} B`;

function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4_294_967_296;
  };
}

function IconButton({ title, onClick, children, active = false, disabled = false }: { title: string; onClick: () => void; children: ReactNode; active?: boolean; disabled?: boolean }) {
  return <button className={`icon-button ${active ? "active" : ""}`} title={title} aria-label={title} onClick={onClick} disabled={disabled}>{children}</button>;
}

export function Dashboard() {
  const [configuration, setConfiguration] = useState<SimulationConfig>(INITIAL_CONFIG);
  const [routingPolicy, setRoutingPolicy] = useState<RoutingPolicy>("contact_aware_earliest_arrival");
  const [seed, setSeed] = useState(42);
  const [randomCount, setRandomCount] = useState(12);
  const [horizonSeconds, setHorizonSeconds] = useState(600);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(INITIAL_CONFIG.bundles[0].bundle_id);
  const [historySelectedBundleId, setHistorySelectedBundleId] = useState<string | null>(null);
  const [transferBundleLimit, setTransferBundleLimit] = useState(12);
  const [expandedTransferBundleIds, setExpandedTransferBundleIds] = useState<Set<string>>(new Set());
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [followPacket, setFollowPacket] = useState(true);
  const [viewMode, setViewMode] = useState<"globe" | "topology">("globe");
  const [activeTab, setActiveTab] = useState<"simulation" | "scenarios">("simulation");
  const [loadedScenarioName, setLoadedScenarioName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const snapshotRef = useRef<SimulationSnapshot | null>(null);
  const [manualNodeId, setManualNodeId] = useState("SAT-NEW");
  const [manualOrbit, setManualOrbit] = useState({ altitude_km: 550, inclination_deg: 53, raan_deg: 0, phase_deg: 0 });
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactDraft, setContactDraft] = useState({ from: "GS-MUMBAI", to: "SAT-01", start: "0", end: "10", rate: "100" });
  const [advanced, setAdvanced] = useState({ ttlSeconds: 21600, bundleSizeMb: 50, bufferGb: 10, linkRateMbps: 100, trafficIntervalSeconds: 60 });

  useEffect(() => { snapshotRef.current = snapshot; }, [snapshot]);

  const runAction = useCallback(async (action: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await action(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unexpected API error"); }
    finally { setBusy(false); }
  }, []);

  const refreshMetrics = useCallback(async (id: string) => {
    try { setMetrics(await getMetrics(id)); } catch { /* the snapshot remains useful if metrics are temporarily unavailable */ }
  }, []);

  const simulationId = snapshot?.simulation_id;
  useEffect(() => {
    if (!simulationId || snapshot?.status !== "running") return;
    let stopped = false;
    const timer = window.setInterval(async () => {
      if (stopped || inFlight.current) return;
      const current = snapshotRef.current;
      if (!current || current.status !== "running") return;
      inFlight.current = true;
      try {
        const result = configuration.orbital_contact_generation
          ? { simulation: await getSimulation(current.simulation_id) }
          : await advanceSimulation(current.simulation_id, Math.min(current.time_us + Math.round(1_000_000 * playbackSpeed), current.horizon_us));
        if (!stopped) {
          setSnapshot(result.simulation);
            const selected = result.simulation.bundles.find((bundle) => bundle.bundle_id === selectedBundleId);
            if ((!selected || ["delivered", "expired", "rejected_at_source"].includes(selected.status)) && selectedBundleId !== historySelectedBundleId) {
              const liveBundles = result.simulation.bundles.filter((bundle) => !["delivered", "expired", "rejected_at_source"].includes(bundle.status));
              const newest = [...liveBundles].sort((a, b) => a.creation_time_us - b.creation_time_us || a.bundle_id.localeCompare(b.bundle_id)).at(-1);
              if (newest) setSelectedBundleId(newest.bundle_id);
            }
          await refreshMetrics(current.simulation_id);
        }
      } catch (cause) {
        if (!stopped) setError(cause instanceof Error ? cause.message : "Simulation advance failed");
      } finally { inFlight.current = false; }
    }, 120);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [simulationId, snapshot?.status, selectedBundleId, historySelectedBundleId, configuration.orbital_contact_generation, playbackSpeed, refreshMetrics]);

  const addManualSatellite = () => {
    const id = manualNodeId.trim();
    if (!id || configuration.nodes.some((node) => node.node_id === id)) { setError("Choose a unique, non-empty satellite ID."); return; }
    if (manualOrbit.altitude_km < 100 || manualOrbit.altitude_km > 2000) { setError("Choose an altitude from 100 to 2,000 km for this simplified LEO model."); return; }
    setConfiguration((current) => ({ ...current, nodes: [...current.nodes, { node_id: id, kind: "satellite", buffer_capacity_bytes: advanced.bufferGb * 1_000_000_000, position_km: null, orbit: manualOrbit }] }));
    setManualNodeId(`SAT-${String(configuration.nodes.length + 1).padStart(2, "0")}`);
  };

  const addRandomSatellites = () => {
    const existingSatelliteCount = configuration.nodes.filter((node) => node.kind === "satellite").length;
    const random = seededRandom(seed + existingSatelliteCount * 9973);
    const existingIds = new Set(configuration.nodes.map((node) => node.node_id));
    const added: NodeConfig[] = [];
    let index = 1;
    while (added.length < randomCount) {
      const id = `SAT-R${String(index++).padStart(3, "0")}`;
      if (existingIds.has(id)) continue;
      const altitude = 400 + random() * 800;
      added.push({
        node_id: id, kind: "satellite", buffer_capacity_bytes: advanced.bufferGb * 1_000_000_000,
        position_km: null,
        orbit: { altitude_km: altitude, inclination_deg: 30 + random() * 60, raan_deg: random() * 360, phase_deg: random() * 360 },
      });
    }
    setConfiguration((current) => ({ ...current, nodes: [...current.nodes, ...added] }));
    setError(null);
  };

  const addContact = () => {
    const id = `C-${contactDraft.from}-${contactDraft.to}-${configuration.contacts.length + 1}`;
    if (contactDraft.from === contactDraft.to) { setError("A contact must connect two different nodes."); return; }
    const contact: ContactConfig = {
      contact_id: id, from_node: contactDraft.from, to_node: contactDraft.to,
      start_us: Math.round(Number(contactDraft.start) * 1_000_000),
      end_us: Math.round(Number(contactDraft.end) * 1_000_000),
      rate_bits_per_second: Math.round(Number(contactDraft.rate || advanced.linkRateMbps) * 1_000_000),
      propagation_delay_us: 0,
    };
    if (!Number.isFinite(contact.start_us) || !Number.isFinite(contact.end_us) || !Number.isFinite(contact.rate_bits_per_second)) { setError("Contact values must be numeric."); return; }
    setConfiguration((current) => ({ ...current, contacts: [...current.contacts, contact] }));
    setShowContactForm(false); setError(null);
  };

  const removeNode = (nodeId: string) => {
    if (configuration.nodes.filter((node) => node.kind === "satellite").length <= 1 && configuration.nodes.find((node) => node.node_id === nodeId)?.kind === "satellite") {
      setError("Keep at least one satellite in the network."); return;
    }
    setConfiguration((current) => ({
      ...current,
      nodes: current.nodes.filter((node) => node.node_id !== nodeId),
      contacts: current.contacts.filter((contact) => contact.from_node !== nodeId && contact.to_node !== nodeId),
      bundles: current.bundles.filter((bundle) => bundle.source !== nodeId && bundle.destination !== nodeId),
    }));
  };

  const startNewSimulation = () => runAction(async () => {
    const created = await createSimulation(configuration, routingPolicy, seed, horizonSeconds * 1_000_000);
    if (playbackSpeed !== 1) await setSimulationPlaybackSpeed(created.simulation_id, playbackSpeed);
    const initial = await postControl(created.simulation_id, "start");
    setSnapshot(initial); setMetrics(null); setSelectedBundleId(configuration.bundles[0]?.bundle_id ?? null);
    setHistorySelectedBundleId(null);
    setTransferBundleLimit(12);
    setExpandedTransferBundleIds(new Set());
    setPlaybackSpeed(initial.playback_speed);
    setFollowPacket(true);
    if (configuration.bundles[0]) setSelectedBundleId(configuration.bundles[0].bundle_id);
  });

  const sendControl = (action: "start" | "pause" | "resume" | "step" | "reset") => {
    if (!snapshot) return;
    runAction(async () => {
      const latest = await postControl(snapshot.simulation_id, action);
      setSnapshot(latest);
      if (action === "reset") {
        setPlaybackSpeed(latest.playback_speed);
        setHistorySelectedBundleId(null);
        setExpandedTransferBundleIds(new Set());
        setTransferBundleLimit(12);
      }
      await refreshMetrics(snapshot.simulation_id);
    });
  };

  const changePlaybackSpeed = (speed: PlaybackSpeed) => {
    setPlaybackSpeed(speed);
    if (!snapshot) return;
    runAction(async () => {
      const latest = await setSimulationPlaybackSpeed(snapshot.simulation_id, speed);
      setSnapshot(latest);
    });
  };

  const addBundle = () => {
    const source = configuration.nodes.find((node) => node.kind === "ground_station")?.node_id ?? configuration.nodes[0]?.node_id;
    const destination = [...configuration.nodes].reverse().find((node) => node.node_id !== source)?.node_id;
    if (!source || !destination) { setError("Add at least two nodes before creating a bundle."); return; }
    const bundle: BundleConfig = {
      bundle_id: `BND-${String(configuration.bundles.length + 1).padStart(3, "0")}`,
      source, destination, payload_bytes: Math.round(advanced.bundleSizeMb * 1_000_000), creation_time_us: 2_000_000, ttl_us: Math.round(advanced.ttlSeconds * 1_000_000),
    };
    setConfiguration((current) => ({ ...current, bundles: [...current.bundles, bundle] }));
    setSelectedBundleId(bundle.bundle_id);
  };

  const activeNode = useMemo(() => {
    const source = snapshot?.nodes ?? configuration.nodes.map((node) => ({ ...node, buffer_occupancy_bytes: 0 }));
    return source.find((node) => node.node_id === selectedNodeId) ?? null;
  }, [snapshot, configuration.nodes, selectedNodeId]);
  const transferBundles = useMemo(() => [...(snapshot?.bundles ?? [])]
    .sort((a, b) => b.creation_time_us - a.creation_time_us || b.bundle_id.localeCompare(a.bundle_id)), [snapshot?.bundles]);
  const selectedBundle: BundleState | null = useMemo(() =>
    snapshot?.bundles.find((bundle) => bundle.bundle_id === selectedBundleId) ??
    (configuration.bundles.find((bundle) => bundle.bundle_id === selectedBundleId)
      ? { ...configuration.bundles.find((bundle) => bundle.bundle_id === selectedBundleId)!, expiry_time_us: configuration.bundles.find((bundle) => bundle.bundle_id === selectedBundleId)!.creation_time_us + configuration.bundles.find((bundle) => bundle.bundle_id === selectedBundleId)!.ttl_us, holder: configuration.bundles.find((bundle) => bundle.bundle_id === selectedBundleId)!.source, status: "queued", forwarding_history: [] }
      : null),
  [snapshot, configuration.bundles, selectedBundleId]);

  const status: RunStatus = snapshot?.status ?? "ready";
  const routingDescription = routingPolicy === "contact_aware_earliest_arrival"
    ? "Chooses the next hop using the configured future contact plan."
    : "Chooses the route with the fewest configured hops; timing is still enforced by contacts.";
  const startDisabled = busy || status === "running" || !configuration.nodes.length;
  const loadScenarioPreset = (scenario: { name: string; configuration: SimulationConfig }) => {
    const nextConfiguration = cloneScenarioConfiguration(scenario.configuration);
    setError(null);
    setConfiguration(nextConfiguration);
    setLoadedScenarioName(scenario.name);
    setAdvanced({
      ttlSeconds: Math.round((nextConfiguration.bundles[0]?.ttl_us ?? 21_600_000_000) / 1_000_000),
      bundleSizeMb: (nextConfiguration.bundles[0]?.payload_bytes ?? 50_000_000) / 1_000_000,
      bufferGb: Math.max(0, ...nextConfiguration.nodes.map((node) => node.buffer_capacity_bytes / 1_000_000_000)),
      linkRateMbps: (nextConfiguration.orbital_link_rate_bits_per_second ?? nextConfiguration.contacts[0]?.rate_bits_per_second ?? 100_000_000) / 1_000_000,
      trafficIntervalSeconds: (nextConfiguration.bundle_generation_interval_us ?? 60_000_000) / 1_000_000,
    });
    setHorizonSeconds(nextConfiguration.orbital_contact_generation
      ? 600
      : Math.max(1, Math.ceil(Math.max(0, ...nextConfiguration.contacts.map((contact) => contact.end_us)) / 1_000_000)));
    setActiveTab("simulation");
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><Globe2 size={22} /></div><div><b>LEO-DTN</b><span>Satellite Network Simulator</span></div></div>
        <nav className="top-nav"><button className={`nav-item ${activeTab === "simulation" ? "selected" : ""}`} onClick={() => setActiveTab("simulation")}><Play size={15} /> Simulation</button><button className="nav-item" disabled title="Experiment analysis is not implemented yet"><Activity size={15} /> Experiments</button><button className={`nav-item ${activeTab === "scenarios" ? "selected" : ""}`} onClick={() => setActiveTab("scenarios")}><Layers3 size={15} /> Scenarios</button></nav>
        <div className="status-chip"><span className={`status-dot ${status}`} /><div><b>{status === "ready" ? "Simulator Ready" : status[0].toUpperCase() + status.slice(1)}</b><small>t = {snapshot ? seconds(snapshot.time_us) : "0.00 s"}</small></div></div>
        <button className="primary top-run" onClick={() => activeTab === "scenarios" ? setActiveTab("simulation") : snapshot ? sendControl(status === "paused" ? "resume" : "start") : startNewSimulation()} disabled={activeTab === "simulation" && (busy || status === "running" || status === "completed" || status === "failed")}>
          {activeTab === "scenarios" ? <Play size={16} /> : busy ? <LoaderCircle className="spin" size={16} /> : status === "running" ? <Activity size={16} /> : <Play size={16} />}
          {activeTab === "scenarios" ? "Back to simulation" : snapshot ? status === "paused" ? "Resume" : status === "running" ? "Running" : "Run Simulation" : "Run Simulation"}
        </button>
      </header>

      {activeTab === "scenarios" ? <ScenarioLibrary canLoadPreset={status !== "running"} onLoadPreset={loadScenarioPreset} /> : <div className="dashboard-grid">
        <aside className="left-column">
          <section className="panel setup-panel">
            <div className="panel-heading"><div className="heading-icon blue"><Waypoints size={16} /></div><h2>Simulation setup</h2><span className="section-tag">CONFIG</span></div>
            <label className="field-label">Scenario</label>
            <button className="select-control scenario-picker-button" onClick={() => setActiveTab("scenarios")}><span>{loadedScenarioName ?? "Custom LEO network"}</span><Layers3 size={14} /></button>
            <p className="algorithm-copy">{loadedScenarioName ? "Preset loaded. Changes apply to the next simulation run." : "Build a custom network here or choose a preset scenario."}</p>
            <label className="field-label">Routing algorithm</label>
            <select className="select-control" value={routingPolicy} onChange={(event) => setRoutingPolicy(event.target.value as RoutingPolicy)}>
              <option value="contact_aware_earliest_arrival">Contact-aware earliest arrival</option>
              <option value="static_minimum_hop">Static minimum hop</option>
            </select>
            <p className="algorithm-copy">{routingDescription}</p>
            <div className="field-row"><label className="field-label" htmlFor="seed">Random seed</label><input id="seed" type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></div>
            <div className="field-row"><label className="field-label" htmlFor="horizon">{configuration.orbital_contact_generation ? "Minimum contact plan (s)" : "Run horizon (s)"}</label><input id="horizon" type="number" min="1" value={horizonSeconds} onChange={(event) => setHorizonSeconds(Number(event.target.value))} /></div>
            {configuration.orbital_contact_generation && <p className="algorithm-copy">The plan expands through bundle TTL so routing can compare full paths before a contact passes.</p>}
            <button className="primary full-width" onClick={startNewSimulation} disabled={startDisabled}><Play size={15} /> Create and run</button>
            <div className="control-row">
              <IconButton title={status === "running" ? "Pause simulation" : status === "paused" ? "Resume simulation" : "Start simulation"} onClick={() => sendControl(status === "running" ? "pause" : status === "paused" ? "resume" : "start")} active={status === "running"} disabled={!snapshot || busy || status === "completed" || status === "failed"}>{status === "running" ? <Pause size={16} /> : <Play size={16} />}</IconButton>
              <IconButton title="Step one simulation event" onClick={() => sendControl("step")} disabled={!snapshot || busy || status === "running" || status === "completed" || status === "failed"}><SkipForward size={16} /></IconButton>
              <IconButton title="Reset simulation" onClick={() => sendControl("reset")} disabled={!snapshot || busy}><RotateCcw size={16} /></IconButton>
              <span className="control-hint">{snapshot ? `${snapshot.events.length} recorded events` : "No active run"}</span>
            </div>
          </section>

        <section className="panel config-panel">
            <div className="panel-heading"><div className="heading-icon cyan"><Satellite size={16} /></div><h2>Satellite configuration</h2><span className="count-pill">{configuration.nodes.filter((node) => node.kind === "satellite").length}</span></div>
            <div className="subheading"><span>Constellation nodes</span><small>Changes apply to the next run</small></div>
            <div className="node-list">
              {configuration.nodes.filter((node) => node.kind === "satellite").map((node) => (
                <div className="node-config-row" key={node.node_id}>
                  <span className="sat-mini"><Satellite size={13} /></span>
                  <button className="node-name" onClick={() => setSelectedNodeId(node.node_id)}>{node.node_id}</button>
                  <span className="coords">{node.orbit ? `${Math.round(node.orbit.altitude_km)} km orbit` : "static point"}</span>
                  <button className="remove-button" title={`Remove ${node.node_id}`} onClick={() => removeNode(node.node_id)}>×</button>
                </div>
              ))}
            </div>
            <div className="manual-add">
              <div className="compact-field"><label htmlFor="satellite-id">Satellite ID</label><input id="satellite-id" value={manualNodeId} onChange={(event) => setManualNodeId(event.target.value)} /></div>
              <div className="form-two orbital-fields">
                <label>Altitude km<input type="number" min="100" max="2000" value={manualOrbit.altitude_km} onChange={(event) => setManualOrbit((orbit) => ({ ...orbit, altitude_km: Number(event.target.value) }))} /></label>
                <label>Inclination °<input type="number" min="0" max="180" value={manualOrbit.inclination_deg} onChange={(event) => setManualOrbit((orbit) => ({ ...orbit, inclination_deg: Number(event.target.value) }))} /></label>
                <label>RAAN °<input type="number" min="0" max="360" value={manualOrbit.raan_deg} onChange={(event) => setManualOrbit((orbit) => ({ ...orbit, raan_deg: Number(event.target.value) }))} /></label>
                <label>Orbit phase °<input type="number" min="0" max="360" value={manualOrbit.phase_deg} onChange={(event) => setManualOrbit((orbit) => ({ ...orbit, phase_deg: Number(event.target.value) }))} /></label>
              </div>
              <button className="secondary full-width" onClick={addManualSatellite}><Plus size={14} /> Add satellite manually</button>
            </div>
            <div className="random-box">
              <div className="random-title"><Sparkles size={14} /><b>Seeded random placement</b></div>
              <div className="random-controls"><label>Count<input type="number" min="1" max="500" value={randomCount} onChange={(event) => setRandomCount(Math.max(1, Math.min(500, Number(event.target.value))))} /></label><button className="secondary" onClick={addRandomSatellites}>Add satellites</button></div>
              <small>Seed {seed} and the current count reproduce these positions.</small>
            </div>
          </section>

          <section className="panel advanced-panel">
            <div className="panel-heading"><div className="heading-icon violet"><Activity size={15} /></div><h2>Advanced parameters</h2></div>
            <div className="advanced-grid">
              <label>Bundle TTL (s)<input type="number" min="1" value={advanced.ttlSeconds} onChange={(event) => setAdvanced((current) => ({ ...current, ttlSeconds: Number(event.target.value) }))} /></label>
              <label>Bundle size (MB)<input type="number" min="0.001" step="0.1" value={advanced.bundleSizeMb} onChange={(event) => setAdvanced((current) => ({ ...current, bundleSizeMb: Number(event.target.value) }))} /></label>
              <label>Buffer capacity (GB)<input type="number" min="0" step="0.5" value={advanced.bufferGb} onChange={(event) => setAdvanced((current) => ({ ...current, bufferGb: Number(event.target.value) }))} /></label>
              <label>Link data rate (Mbps)<input type="number" min="0.001" value={advanced.linkRateMbps} onChange={(event) => setAdvanced((current) => ({ ...current, linkRateMbps: Number(event.target.value) }))} /></label>
              <label>Bundle interval (s)<input type="number" min="1" value={advanced.trafficIntervalSeconds} onChange={(event) => { const seconds = Math.max(1, Number(event.target.value)); setAdvanced((current) => ({ ...current, trafficIntervalSeconds: seconds })); if (configuration.bundle_generation_interval_us != null) setConfiguration((current) => ({ ...current, bundle_generation_interval_us: Math.round(seconds * 1_000_000) })); }} /></label>
            </div>
            <button className="secondary full-width" onClick={() => setConfiguration((current) => ({
              ...current,
              nodes: current.nodes.map((node) => ({ ...node, buffer_capacity_bytes: Math.round(advanced.bufferGb * 1_000_000_000) })),
              contacts: current.contacts.map((contact) => ({ ...contact, rate_bits_per_second: Math.round(advanced.linkRateMbps * 1_000_000) })),
              bundles: current.bundles.map((bundle) => ({ ...bundle, payload_bytes: Math.round(advanced.bundleSizeMb * 1_000_000), ttl_us: Math.round(advanced.ttlSeconds * 1_000_000) })),
              orbital_link_rate_bits_per_second: Math.round(advanced.linkRateMbps * 1_000_000),
            }))}>Apply to current configuration</button>
          </section>

          <section className="panel plan-panel">
            <div className="panel-heading"><div className="heading-icon violet"><Link2 size={16} /></div><h2>Contact plan</h2><button className="quiet-button" onClick={() => setShowContactForm((value) => !value)}><Plus size={14} /> Add manual</button></div>
            <label className="geometry-toggle"><input type="checkbox" checked={configuration.orbital_contact_generation ?? false} onChange={(event) => setConfiguration((current) => ({ ...current, orbital_contact_generation: event.target.checked }))} /><span>Generate links from live orbital visibility</span></label>
            {configuration.orbital_contact_generation && <div className="geometry-settings"><label>Minimum station elevation °<input type="number" min="0" max="45" value={configuration.minimum_elevation_deg ?? 10} onChange={(event) => setConfiguration((current) => ({ ...current, minimum_elevation_deg: Number(event.target.value) }))} /></label><label>Geometry sampling (s)<input type="number" min="1" max="300" value={(configuration.contact_sample_interval_us ?? 10_000_000) / 1_000_000} onChange={(event) => setConfiguration((current) => ({ ...current, contact_sample_interval_us: Math.max(100_000, Number(event.target.value) * 1_000_000) }))} /></label></div>}
            <label className="geometry-toggle"><input type="checkbox" checked={configuration.bundle_generation_interval_us != null} onChange={(event) => setConfiguration((current) => ({ ...current, bundle_generation_interval_us: event.target.checked ? Math.round(advanced.trafficIntervalSeconds * 1_000_000) : null }))} /><span>Keep generating bundles at the selected interval</span></label>
            <div className="contact-list">{configuration.contacts.map((contact) => <div className="contact-row" key={contact.contact_id}><span className="contact-led" /><div><b>{contact.from_node} → {contact.to_node}</b><small>{seconds(contact.start_us)}–{seconds(contact.end_us)} · {contact.rate_bits_per_second / 1_000_000} Mbps</small></div><button className="remove-button" title="Remove contact" onClick={() => setConfiguration((current) => ({ ...current, contacts: current.contacts.filter((item) => item.contact_id !== contact.contact_id) }))}>×</button></div>)}</div>
            {showContactForm && <div className="contact-form">
              <div className="form-two"><label>From<select value={contactDraft.from} onChange={(event) => setContactDraft((draft) => ({ ...draft, from: event.target.value }))}>{configuration.nodes.map((node) => <option key={node.node_id}>{node.node_id}</option>)}</select></label><label>To<select value={contactDraft.to} onChange={(event) => setContactDraft((draft) => ({ ...draft, to: event.target.value }))}>{configuration.nodes.map((node) => <option key={node.node_id}>{node.node_id}</option>)}</select></label></div>
              <div className="form-three"><label>Start s<input type="number" min="0" value={contactDraft.start} onChange={(event) => setContactDraft((draft) => ({ ...draft, start: event.target.value }))} /></label><label>End s<input type="number" min="0.001" value={contactDraft.end} onChange={(event) => setContactDraft((draft) => ({ ...draft, end: event.target.value }))} /></label><label>Mbps<input type="number" min="0.001" value={contactDraft.rate} onChange={(event) => setContactDraft((draft) => ({ ...draft, rate: event.target.value }))} /></label></div>
              <button className="secondary full-width" onClick={addContact}>Add scheduled contact</button>
            </div>}
            <div className="bundle-config"><div className="subheading"><span>Bundles</span><button className="quiet-button" onClick={addBundle}><Plus size={13} /> Add bundle</button></div>
              {configuration.bundles.map((bundle) => <div className="bundle-config-row" key={bundle.bundle_id}><span className="bundle-dot" /><div><b>{bundle.bundle_id}</b><small>{bundle.source} → {bundle.destination} · {bytes(bundle.payload_bytes)}</small></div><button className="remove-button" onClick={() => setConfiguration((current) => ({ ...current, bundles: current.bundles.filter((item) => item.bundle_id !== bundle.bundle_id) }))}>×</button></div>)}
            </div>
          </section>
        </aside>

        <section className="visual-column">
          <div className="visual-toolbar"><div><h1>Network visualization</h1><p>{snapshot ? `${snapshot.nodes.length} nodes · ${snapshot.contacts.length} contacts · ${snapshot.routing_policy.replaceAll("_", " ")}` : "Configure a contact plan, then create a simulation run."}</p></div><div className="view-switch"><button className={viewMode === "globe" ? "selected" : ""} onClick={() => setViewMode("globe")}><Globe2 size={14} /> 3D Globe</button><button disabled title="Contact positions are not Earth latitude and longitude yet"><Layers3 size={14} /> 2D Map</button><button className={viewMode === "topology" ? "selected" : ""} onClick={() => setViewMode("topology")}><Waypoints size={14} /> Topology</button></div></div>
          <div className="scene-frame">
            {viewMode === "globe" ? <NetworkScene snapshot={snapshot} selectedBundleId={selectedBundleId} followPacket={followPacket} onSelectNode={setSelectedNodeId} onSelectBundle={setSelectedBundleId} /> : <NetworkTopology snapshot={snapshot} selectedBundleId={selectedBundleId} onSelectNode={setSelectedNodeId} />}
            {viewMode === "globe" && <div className="scene-overlay scene-help"><CircleHelp size={13} /> Drag to rotate view · Scroll to zoom</div>}
            <div className="scene-legend"><span><i className="legend-line active-line" /> Active contact</span><span><i className="legend-line planned-line" /> Scheduled contact</span><span><i className="legend-line orbit-line" /> Orbit trace</span><span><i className="legend-dot sat-legend" /> Satellite</span><span><i className="legend-dot ground-legend" /> Ground station</span><span><i className="legend-dot bundle-legend" /> Bundles · click to inspect</span></div>
            {!snapshot && <div className="scene-empty"><div className="empty-globe"><Globe2 size={32} /></div><b>Ready for a contact plan</b><span>Satellite positions and links will appear from the configured simulation state.</span><button className="primary" onClick={startNewSimulation}><Play size={15} /> Create simulation</button></div>}
            {error && <div className="error-banner"><AlertCircle size={15} />{error}<button onClick={() => setError(null)}>×</button></div>}
          </div>
          <div className="playback-bar">
            <div className="playback-actions">
              <IconButton title={status === "running" ? "Pause simulation" : status === "paused" ? "Resume simulation" : "Start simulation"} onClick={() => sendControl(status === "running" ? "pause" : status === "paused" ? "resume" : "start")} active={status === "running"} disabled={!snapshot || busy || status === "completed" || status === "failed"}>{status === "running" ? <Pause size={17} /> : <Play size={17} />}</IconButton>
              <IconButton title="Step one simulation event" onClick={() => sendControl("step")} disabled={!snapshot || busy || status === "running" || status === "completed" || status === "failed"}><SkipForward size={17} /></IconButton>
              <IconButton title="Reset simulation" onClick={() => sendControl("reset")} disabled={!snapshot || busy}><RotateCcw size={16} /></IconButton>
            </div>
            <div className="timeline"><div className="time-label"><b>t = {snapshot ? seconds(snapshot.time_us) : "0.00 s"}</b><span>{snapshot ? configuration.orbital_contact_generation ? `Live · contacts planned to ${seconds(snapshot.horizon_us)}` : `/ ${seconds(snapshot.horizon_us)}` : "No run"}</span></div><div className="timeline-track"><div className="timeline-progress" style={{ width: `${snapshot ? Math.min(100, (snapshot.time_us / snapshot.horizon_us) * 100) : 0}%` }} /><span className="timeline-thumb" style={{ left: `${snapshot ? Math.min(100, (snapshot.time_us / snapshot.horizon_us) * 100) : 0}%` }} /></div></div>
            <label className="playback-speed"><span>Speed</span><select aria-label="Simulation playback speed" value={playbackSpeed} onChange={(event) => changePlaybackSpeed(Number(event.target.value) as PlaybackSpeed)} disabled={busy}><option value={0.25}>0.25×</option><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label>
            <button className={`follow-button ${followPacket ? "enabled" : ""}`} onClick={() => setFollowPacket((value) => !value)} disabled={!selectedBundleId || viewMode !== "globe"} title={viewMode === "globe" ? "Keep the selected bundle centered in the 3D view" : "Packet-follow is available in the 3D globe view"}><Sparkles size={14} /> {followPacket ? "Following bundle" : "Follow bundle"}</button>
          </div>
          <div className="summary-strip"><Metric label="Delivered" value={metrics ? `${metrics.delivered_count}/${metrics.generated_count}` : "—"} tone="green" /><Metric label="Delivery ratio" value={metrics?.delivery_ratio == null ? "—" : `${(metrics.delivery_ratio * 100).toFixed(1)}%`} tone="blue" /><Metric label="Mean latency" value={metrics?.mean_delivery_latency_us == null ? "—" : seconds(metrics.mean_delivery_latency_us)} tone="cyan" /><Metric label="Contact use" value={metrics?.contact_utilization_fraction == null ? "—" : `${(metrics.contact_utilization_fraction * 100).toFixed(1)}%`} tone="purple" /></div>
        </section>

        <aside className="right-column">
          <section className="panel details-panel">
            <div className="panel-heading"><div className="heading-icon amber"><Activity size={15} /></div><h2>Bundle details</h2><ChevronDown size={15} className="muted-icon" /></div>
            {selectedBundle ? <>
              <div className="bundle-id-line"><span className={`bundle-status ${selectedBundle.status}`} /> <b>{selectedBundle.bundle_id}</b><span className="status-label">{selectedBundle.status.replaceAll("_", " ")}</span></div>
              <InfoRow label="Source" value={selectedBundle.source} /><InfoRow label="Destination" value={selectedBundle.destination} /><InfoRow label="Payload" value={bytes(selectedBundle.payload_bytes)} /><InfoRow label="Created" value={seconds(selectedBundle.creation_time_us)} /><InfoRow label="Expires" value={seconds(selectedBundle.expiry_time_us)} /><InfoRow label="Current holder" value={selectedBundle.holder ?? (selectedBundle.status === "delivered" ? "At destination" : selectedBundle.status === "transmitting" || selectedBundle.status === "in_transit" ? "In transit" : "No holder")} />
              {snapshot && selectedBundle.status === "queued" && selectedBundle.holder && selectedBundle.holder !== selectedBundle.destination && <div className="bundle-wait-note"><span className="wait-pulse" /><div><b>Stored at {selectedBundle.holder}</b><small>{snapshot.status === "completed" ? "No feasible forwarding opportunity was found before this run horizon." : "Waiting for a future contact. The bundle stays here until the engine starts a valid next transfer."}</small></div></div>}
              <div className="path-heading">Forwarding history <small>{selectedBundle.forwarding_history.length} hops</small></div>
              {selectedBundle.forwarding_history.length ? <div className="path-list">{selectedBundle.forwarding_history.map((hop, index) => <div className="path-step" key={`${hop.contact_id}-${index}`}><span className="path-dot" /><div><b>{hop.from_node} → {hop.to_node}</b><small>{hop.contact_id} · {seconds(hop.receiver_acceptance_us)}</small></div></div>)}</div> : <p className="empty-copy">Forwarding hops appear after the engine records successful contact transfers.</p>}
            </> : <p className="empty-copy">Select a configured bundle to inspect its state and journey.</p>}
          </section>

          <section className="panel network-status-panel">
            <div className="panel-heading"><div className="heading-icon cyan"><Activity size={15} /></div><h2>Network status</h2><span className="live-indicator"><i /> {snapshot?.status ?? "idle"}</span></div>
            <InfoRow label="Active contacts" value={`${snapshot?.contacts.filter((contact) => contact.status === "active").length ?? 0} / ${snapshot?.contacts.length ?? configuration.contacts.length}`} accent="green" />
            <InfoRow label="Total satellites" value={String(snapshot?.nodes.filter((node) => node.kind === "satellite").length ?? configuration.nodes.filter((node) => node.kind === "satellite").length)} />
            <InfoRow label="Ground stations" value={String(snapshot?.nodes.filter((node) => node.kind === "ground_station").length ?? configuration.nodes.filter((node) => node.kind === "ground_station").length)} />
            <InfoRow label="Queued bundles" value={String(snapshot?.bundles.filter((bundle) => bundle.status === "queued").length ?? 0)} />
            <InfoRow label="Delivered" value={String(metrics?.delivered_count ?? 0)} accent="green" />
            <InfoRow label="Expired" value={String(metrics?.expired_count ?? 0)} accent="red" />
          </section>

          <section className="panel transfer-history-panel">
            <div className="panel-heading"><div className="heading-icon violet"><History size={15} /></div><h2>Transfers by bundle</h2><span className="transfer-count">{transferBundles.length} bundles</span></div>
            {!snapshot ? <p className="empty-copy">Transfers from this run will be recorded here.</p> : transferBundles.length === 0 ? <p className="empty-copy">No bundles have been generated in this run yet.</p> : <>
              <div className="transfer-history-list" aria-label="Bundle transfer history for this simulation run">
                {transferBundles.slice(0, transferBundleLimit).map((bundle) => <details className="transfer-bundle-group" key={bundle.bundle_id} open={expandedTransferBundleIds.has(bundle.bundle_id)} onToggle={(event) => {
                  const isOpen = event.currentTarget.open;
                  setExpandedTransferBundleIds((current) => {
                    const next = new Set(current);
                    if (isOpen) next.add(bundle.bundle_id); else next.delete(bundle.bundle_id);
                    return next;
                  });
                }}>
                  <summary className="transfer-bundle-summary" onClick={() => { setHistorySelectedBundleId(bundle.bundle_id); setSelectedBundleId(bundle.bundle_id); }}>
                    <span className={`bundle-status ${bundle.status}`} />
                    <span className="transfer-bundle-heading"><b>{bundle.bundle_id}</b><small>{bundle.source} → {bundle.destination}</small></span>
                    <span className={`transfer-bundle-status ${bundle.status}`}>{bundle.status.replaceAll("_", " ")}</span>
                    <span className="transfer-bundle-count">{bundle.forwarding_history.length} hops</span>
                  </summary>
                  <div className="transfer-bundle-hops">
                    {bundle.forwarding_history.length ? bundle.forwarding_history.map((hop, index) => <button className="transfer-history-row" key={`${hop.contact_id}-${hop.receiver_acceptance_us}-${index}`} onClick={() => { setHistorySelectedBundleId(bundle.bundle_id); setSelectedBundleId(bundle.bundle_id); }}>
                      <span className="transfer-history-time">{seconds(hop.receiver_acceptance_us)}</span>
                      <span className="transfer-history-content"><b>{hop.from_node} → {hop.to_node}</b><small>{hop.contact_id}</small></span>
                    </button>) : <p className="empty-copy">No successful hops recorded yet.</p>}
                  </div>
                </details>)}
              </div>
              {transferBundles.length > transferBundleLimit && <button className="show-older-transfers" onClick={() => setTransferBundleLimit((count) => Math.min(count + 12, transferBundles.length))}>Show older bundles ({transferBundles.length - transferBundleLimit} remaining)</button>}
              <p className="transfer-history-note">Each bundle keeps its successful hops for this run. Select a bundle or hop to inspect its path.</p>
            </>}
          </section>

          <section className="panel node-info-panel">
            <div className="panel-heading"><div className="heading-icon blue"><Satellite size={15} /></div><h2>Selected node</h2><ChevronDown size={15} className="muted-icon" /></div>
            {activeNode ? <>
              <InfoRow label="ID" value={activeNode.node_id} /><InfoRow label="Type" value={activeNode.kind.replaceAll("_", " ")} /><InfoRow label="Position" value={activeNode.position_km ? `(${activeNode.position_km.map((value) => value.toFixed(0)).join(", ")}) km · ECEF` : "Not specified"} />{activeNode.orbit && <><InfoRow label="Altitude / inclination" value={`${activeNode.orbit.altitude_km.toFixed(0)} km / ${activeNode.orbit.inclination_deg.toFixed(1)}°`} /><InfoRow label="Velocity" value={activeNode.velocity_km_s ? `${Math.hypot(...activeNode.velocity_km_s).toFixed(2)} km/s` : "—"} /></>}<InfoRow label="Buffer" value={`${bytes(activeNode.buffer_occupancy_bytes)} / ${bytes(activeNode.buffer_capacity_bytes)}`} />
            </> : <>
              <p className="empty-copy">Click a satellite or station in the globe to inspect it.</p>
              <div className="node-picker">{(snapshot?.nodes ?? configuration.nodes.map((node) => ({ ...node, buffer_occupancy_bytes: 0, velocity_km_s: null }))).slice(0, 5).map((node) => <button key={node.node_id} onClick={() => setSelectedNodeId(node.node_id)}>{node.node_id}<span>{node.kind === "satellite" ? "SAT" : "GS"}</span></button>)}</div>
            </>}
          </section>
          <div className="data-note"><i /> Positions, line-of-sight windows, transfers, and paths come from the engine. Circular-orbit geometry is simplified and is not an operational prediction.</div>
        </aside>
      </div>}
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="metric-card"><span>{label}</span><b className={tone}>{value}</b></div>;
}

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return <div className="info-row"><span>{label}</span><b className={accent ?? ""}>{value}</b></div>;
}
