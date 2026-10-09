"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Activity, AlertCircle, ChevronDown, CircleHelp, Globe2, Layers3, Link2, LoaderCircle,
  Pause, Play, Plus, RotateCcw, Satellite, SkipForward, Sparkles, Waypoints,
} from "lucide-react";
import { advanceSimulation, createSimulation, getMetrics, postControl } from "@/lib/api";
import type { BundleConfig, BundleState, ContactConfig, Metrics, NodeConfig, RoutingPolicy, RunStatus, SimulationConfig, SimulationSnapshot } from "@/lib/contracts";
import { NetworkScene } from "./network-scene";
import { NetworkTopology } from "./network-topology";

const EARTH_RADIUS_KM = 6371;
const INITIAL_CONFIG: SimulationConfig = {
  nodes: [
    { node_id: "GS-MUMBAI", kind: "ground_station", buffer_capacity_bytes: 10_000_000_000, position_km: [EARTH_RADIUS_KM, 0, 0] },
    { node_id: "SAT-01", kind: "satellite", buffer_capacity_bytes: 10_000_000_000, position_km: [0, 6900, 0] },
    { node_id: "GS-SINGAPORE", kind: "ground_station", buffer_capacity_bytes: 10_000_000_000, position_km: [0, 0, -EARTH_RADIUS_KM] },
  ],
  contacts: [
    { contact_id: "C-MUM-SAT", from_node: "GS-MUMBAI", to_node: "SAT-01", start_us: 0, end_us: 10_000_000, rate_bits_per_second: 100_000_000, propagation_delay_us: 2_000 },
    { contact_id: "C-SAT-SIN", from_node: "SAT-01", to_node: "GS-SINGAPORE", start_us: 20_000_000, end_us: 30_000_000, rate_bits_per_second: 100_000_000, propagation_delay_us: 2_000 },
  ],
  bundles: [
    { bundle_id: "BND-001", source: "GS-MUMBAI", destination: "GS-SINGAPORE", payload_bytes: 5_000_000, creation_time_us: 2_000_000, ttl_us: 3_600_000_000 },
  ],
  interruptions: [],
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

function IconButton({ title, onClick, children, active = false }: { title: string; onClick: () => void; children: ReactNode; active?: boolean }) {
  return <button className={`icon-button ${active ? "active" : ""}`} title={title} aria-label={title} onClick={onClick}>{children}</button>;
}

export function Dashboard() {
  const [configuration, setConfiguration] = useState<SimulationConfig>(INITIAL_CONFIG);
  const [routingPolicy, setRoutingPolicy] = useState<RoutingPolicy>("contact_aware_earliest_arrival");
  const [seed, setSeed] = useState(42);
  const [randomCount, setRandomCount] = useState(12);
  const [horizonSeconds, setHorizonSeconds] = useState(120);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(INITIAL_CONFIG.bundles[0].bundle_id);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [followPacket, setFollowPacket] = useState(false);
  const [viewMode, setViewMode] = useState<"globe" | "topology">("globe");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const snapshotRef = useRef<SimulationSnapshot | null>(null);
  const [manualPosition, setManualPosition] = useState<[number, number, number]>([7000, 0, 0]);
  const [manualNodeId, setManualNodeId] = useState("SAT-NEW");
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactDraft, setContactDraft] = useState({ from: "GS-MUMBAI", to: "SAT-01", start: "0", end: "10", rate: "100" });
  const [advanced, setAdvanced] = useState({ ttlSeconds: 3600, bundleSizeMb: 5, bufferGb: 10, linkRateMbps: 100 });

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
        const target = Math.min(current.time_us + 5_000_000, current.horizon_us);
        const result = await advanceSimulation(current.simulation_id, target);
        if (!stopped) {
          setSnapshot(result.simulation);
          await refreshMetrics(current.simulation_id);
        }
      } catch (cause) {
        if (!stopped) setError(cause instanceof Error ? cause.message : "Simulation advance failed");
      } finally { inFlight.current = false; }
    }, 320);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [simulationId, snapshot?.status, refreshMetrics]);

  const addManualSatellite = () => {
    const id = manualNodeId.trim();
    if (!id || configuration.nodes.some((node) => node.node_id === id)) { setError("Choose a unique, non-empty satellite ID."); return; }
    const orbitalRadius = Math.hypot(...manualPosition);
    if (orbitalRadius <= EARTH_RADIUS_KM) { setError("Satellite coordinates must place it outside the Earth radius (6,371 km)."); return; }
    setConfiguration((current) => ({ ...current, nodes: [...current.nodes, { node_id: id, kind: "satellite", buffer_capacity_bytes: advanced.bufferGb * 1_000_000_000, position_km: manualPosition }] }));
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
      const z = random() * 2 - 1;
      const angle = random() * Math.PI * 2;
      const radius = 6800 + random() * 1400;
      const planar = Math.sqrt(1 - z * z);
      added.push({
        node_id: id, kind: "satellite", buffer_capacity_bytes: advanced.bufferGb * 1_000_000_000,
        position_km: [radius * planar * Math.cos(angle), radius * z, radius * planar * Math.sin(angle)],
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
    const initial = await postControl(created.simulation_id, "start");
    setSnapshot(initial); setMetrics(null); setSelectedBundleId(configuration.bundles[0]?.bundle_id ?? null);
    if (configuration.bundles[0]) setSelectedBundleId(configuration.bundles[0].bundle_id);
  });

  const sendControl = (action: "start" | "pause" | "resume" | "step" | "reset") => {
    if (!snapshot) return;
    runAction(async () => {
      const latest = await postControl(snapshot.simulation_id, action);
      setSnapshot(latest);
      await refreshMetrics(snapshot.simulation_id);
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><Globe2 size={22} /></div><div><b>LEO-DTN</b><span>Satellite Network Simulator</span></div></div>
        <nav className="top-nav"><button className="nav-item selected"><Play size={15} /> Simulation</button><button className="nav-item" disabled><Activity size={15} /> Experiments</button><button className="nav-item" disabled><Layers3 size={15} /> Scenarios</button></nav>
        <div className="status-chip"><span className={`status-dot ${status}`} /><div><b>{status === "ready" ? "Simulator Ready" : status[0].toUpperCase() + status.slice(1)}</b><small>t = {snapshot ? seconds(snapshot.time_us) : "0.00 s"}</small></div></div>
        <button className="primary top-run" onClick={() => snapshot ? sendControl(status === "paused" ? "resume" : "start") : startNewSimulation()} disabled={busy || status === "running" || status === "completed"}>
          {busy ? <LoaderCircle className="spin" size={16} /> : status === "running" ? <Activity size={16} /> : <Play size={16} />}
          {snapshot ? status === "paused" ? "Resume" : status === "running" ? "Running" : "Run Simulation" : "Run Simulation"}
        </button>
      </header>

      <div className="dashboard-grid">
        <aside className="left-column">
          <section className="panel setup-panel">
            <div className="panel-heading"><div className="heading-icon blue"><Waypoints size={16} /></div><h2>Simulation setup</h2><span className="section-tag">CONFIG</span></div>
            <label className="field-label">Scenario</label>
            <select className="select-control" value="custom" onChange={() => undefined}><option value="custom">Custom LEO network</option></select>
            <label className="field-label">Routing algorithm</label>
            <select className="select-control" value={routingPolicy} onChange={(event) => setRoutingPolicy(event.target.value as RoutingPolicy)}>
              <option value="contact_aware_earliest_arrival">Contact-aware earliest arrival</option>
              <option value="static_minimum_hop">Static minimum hop</option>
            </select>
            <p className="algorithm-copy">{routingDescription}</p>
            <div className="field-row"><label className="field-label" htmlFor="seed">Random seed</label><input id="seed" type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></div>
            <div className="field-row"><label className="field-label" htmlFor="horizon">Run horizon (s)</label><input id="horizon" type="number" min="1" value={horizonSeconds} onChange={(event) => setHorizonSeconds(Number(event.target.value))} /></div>
            <button className="primary full-width" onClick={startNewSimulation} disabled={startDisabled}><Play size={15} /> Create and run</button>
            <div className="control-row">
              <IconButton title="Pause simulation" onClick={() => sendControl("pause")} active={status === "running"}><Pause size={16} /></IconButton>
              <IconButton title="Step one simulation event" onClick={() => sendControl("step")}><SkipForward size={16} /></IconButton>
              <IconButton title="Reset simulation" onClick={() => sendControl("reset")}><RotateCcw size={16} /></IconButton>
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
                  <span className="coords">{node.position_km?.map((value) => Math.round(value)).join(", ") ?? "unplaced"} km</span>
                  <button className="remove-button" title={`Remove ${node.node_id}`} onClick={() => removeNode(node.node_id)}>×</button>
                </div>
              ))}
            </div>
            <div className="manual-add">
              <div className="compact-field"><label htmlFor="satellite-id">Satellite ID</label><input id="satellite-id" value={manualNodeId} onChange={(event) => setManualNodeId(event.target.value)} /></div>
              <div className="xyz-grid">
                {(["X", "Y", "Z"] as const).map((axis, index) => <label key={axis}>{axis} km<input type="number" value={manualPosition[index]} onChange={(event) => setManualPosition((position) => position.map((value, i) => i === index ? Number(event.target.value) : value) as [number, number, number])} /></label>)}
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
            </div>
            <button className="secondary full-width" onClick={() => setConfiguration((current) => ({
              ...current,
              nodes: current.nodes.map((node) => ({ ...node, buffer_capacity_bytes: Math.round(advanced.bufferGb * 1_000_000_000) })),
              contacts: current.contacts.map((contact) => ({ ...contact, rate_bits_per_second: Math.round(advanced.linkRateMbps * 1_000_000) })),
              bundles: current.bundles.map((bundle) => ({ ...bundle, payload_bytes: Math.round(advanced.bundleSizeMb * 1_000_000), ttl_us: Math.round(advanced.ttlSeconds * 1_000_000) })),
            }))}>Apply to current configuration</button>
          </section>

          <section className="panel plan-panel">
            <div className="panel-heading"><div className="heading-icon violet"><Link2 size={16} /></div><h2>Contact plan</h2><button className="quiet-button" onClick={() => setShowContactForm((value) => !value)}><Plus size={14} /> Add</button></div>
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
            {viewMode === "globe" ? <NetworkScene snapshot={snapshot} selectedBundleId={selectedBundleId} followPacket={followPacket} onSelectNode={setSelectedNodeId} /> : <NetworkTopology snapshot={snapshot} selectedBundleId={selectedBundleId} onSelectNode={setSelectedNodeId} />}
            {viewMode === "globe" && <div className="scene-overlay scene-help"><CircleHelp size={13} /> Drag to rotate view · Scroll to zoom</div>}
            <div className="scene-legend"><span><i className="legend-line active-line" /> Active contact</span><span><i className="legend-line planned-line" /> Scheduled contact</span><span><i className="legend-dot sat-legend" /> Satellite</span><span><i className="legend-dot ground-legend" /> Ground station</span><span><i className="legend-dot packet-legend" /> Selected bundle</span></div>
            {!snapshot && <div className="scene-empty"><div className="empty-globe"><Globe2 size={32} /></div><b>Ready for a contact plan</b><span>Satellite positions and links will appear from the configured simulation state.</span><button className="primary" onClick={startNewSimulation}><Play size={15} /> Create simulation</button></div>}
            {error && <div className="error-banner"><AlertCircle size={15} />{error}<button onClick={() => setError(null)}>×</button></div>}
          </div>
          <div className="playback-bar">
            <div className="playback-actions"><IconButton title="Pause" onClick={() => sendControl("pause")} active={status === "running"}><Pause size={17} /></IconButton><IconButton title="Step one event" onClick={() => sendControl("step")}><SkipForward size={17} /></IconButton><IconButton title="Reset" onClick={() => sendControl("reset")}><RotateCcw size={16} /></IconButton></div>
            <div className="timeline"><div className="time-label"><b>t = {snapshot ? seconds(snapshot.time_us) : "0.00 s"}</b><span>{snapshot ? `/ ${seconds(snapshot.horizon_us)}` : "No run"}</span></div><div className="timeline-track"><div className="timeline-progress" style={{ width: `${snapshot ? Math.min(100, (snapshot.time_us / snapshot.horizon_us) * 100) : 0}%` }} /><span className="timeline-thumb" style={{ left: `${snapshot ? Math.min(100, (snapshot.time_us / snapshot.horizon_us) * 100) : 0}%` }} /></div></div>
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

          <section className="panel node-info-panel">
            <div className="panel-heading"><div className="heading-icon blue"><Satellite size={15} /></div><h2>Selected node</h2><ChevronDown size={15} className="muted-icon" /></div>
            {activeNode ? <>
              <InfoRow label="ID" value={activeNode.node_id} /><InfoRow label="Type" value={activeNode.kind.replaceAll("_", " ")} /><InfoRow label="Position" value={activeNode.position_km ? `(${activeNode.position_km.map((value) => value.toFixed(0)).join(", ")}) km` : "Not specified"} /><InfoRow label="Buffer" value={`${bytes(activeNode.buffer_occupancy_bytes)} / ${bytes(activeNode.buffer_capacity_bytes)}`} />
            </> : <>
              <p className="empty-copy">Click a satellite or station in the globe to inspect it.</p>
              <div className="node-picker">{(snapshot?.nodes ?? configuration.nodes.map((node) => ({ ...node, buffer_occupancy_bytes: 0 }))).slice(0, 5).map((node) => <button key={node.node_id} onClick={() => setSelectedNodeId(node.node_id)}>{node.node_id}<span>{node.kind === "satellite" ? "SAT" : "GS"}</span></button>)}</div>
            </>}
          </section>
          <div className="data-note"><i /> Displayed links, transfers, and paths come from the simulation engine. Satellite placement stays fixed until a motion model is added.</div>
        </aside>
      </div>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="metric-card"><span>{label}</span><b className={tone}>{value}</b></div>;
}

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return <div className="info-row"><span>{label}</span><b className={accent ?? ""}>{value}</b></div>;
}
