"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, ArrowDownRight, Check, ChevronRight, CircleHelp, Clock3, Globe2, Layers3, LoaderCircle, Radio, Satellite, Waypoints } from "lucide-react";
import { getScenario, getScenarios } from "@/lib/api";
import type { ScenarioDetails, ScenarioSummary, SimulationConfig } from "@/lib/contracts";

interface ScenarioLibraryProps {
  canLoadPreset: boolean;
  onLoadPreset: (scenario: ScenarioDetails) => void;
}

export function ScenarioLibrary({ canLoadPreset, onLoadPreset }: ScenarioLibraryProps) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [selected, setSelected] = useState<ScenarioDetails | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const detailsRequestId = useRef(0);

  useEffect(() => {
    let cancelled = false;
    getScenarios().then((items) => {
      if (cancelled) return;
      setScenarios(items);
      setLoadingList(false);
      if (items[0]) {
        const requestId = ++detailsRequestId.current;
        setLoadingDetails(true);
        getScenario(items[0].scenario_id).then((details) => {
          if (!cancelled && detailsRequestId.current === requestId) setSelected(details);
        }).catch((cause: unknown) => {
          if (!cancelled && detailsRequestId.current === requestId) {
            setError(cause instanceof Error ? cause.message : "Could not load scenario details.");
          }
        }).finally(() => {
          if (!cancelled && detailsRequestId.current === requestId) setLoadingDetails(false);
        });
      }
    }).catch((cause: unknown) => {
      if (!cancelled) {
        setError(cause instanceof Error ? cause.message : "Could not load scenario presets.");
        setLoadingList(false);
      }
    }).finally(() => {
      if (!cancelled) setLoadingList(false);
    });
    return () => { cancelled = true; detailsRequestId.current += 1; };
  }, []);

  const inspect = async (scenarioId: string) => {
    const requestId = ++detailsRequestId.current;
    setLoadingDetails(true);
    setError(null);
    try {
      const details = await getScenario(scenarioId);
      if (detailsRequestId.current === requestId) setSelected(details);
    } catch (cause) {
      if (detailsRequestId.current === requestId) {
        setError(cause instanceof Error ? cause.message : "Could not load scenario details.");
      }
    } finally {
      if (detailsRequestId.current === requestId) setLoadingDetails(false);
    }
  };

  if (loadingList) return <main className="scenario-page"><div className="scenario-loading"><LoaderCircle className="spin" size={20} /> Loading scenario presets…</div></main>;

  return (
    <main className="scenario-page">
      <div className="scenario-page-heading">
        <div><div className="eyebrow">SCENARIO LIBRARY · {scenarios.length} PRESETS</div><h1>Choose a network scenario</h1><p>Each preset sets up a reproducible network and traffic pattern. Inspect its contacts and bundle configuration, then load it into Simulation.</p></div>
        <div className="scenario-help"><CircleHelp size={15} /><span>Loading a preset changes the configuration for your next run. It does not start or alter a simulation.</span></div>
      </div>

      {error && <div className="scenario-error" role="alert"><Activity size={15} />{error}</div>}

      <div className="scenario-layout">
        <div className="scenario-catalog" aria-label="Scenario presets">
          {scenarios.map((scenario, index) => {
            const active = selected?.scenario_id === scenario.scenario_id;
            return <button key={scenario.scenario_id} className={`scenario-card ${active ? "selected" : ""}`} onClick={() => void inspect(scenario.scenario_id)} aria-pressed={active}>
              <div className="scenario-card-top"><span className={`scenario-index ${scenario.orbital_contact_generation ? "orbital" : ""}`}>{String(index + 1).padStart(2, "0")}</span><span className="scenario-type">{scenario.orbital_contact_generation ? "ORBITAL" : "SCHEDULED"}</span></div>
              <div className="scenario-card-icon">{scenario.orbital_contact_generation ? <Globe2 size={19} /> : scenario.satellite_count ? <Satellite size={19} /> : <Radio size={19} />}</div>
              <h2>{scenario.name}</h2><p>{scenario.description}</p>
              <div className="scenario-card-stats"><span><Waypoints size={12} /> {scenario.node_count} nodes</span><span><Layers3 size={12} /> {scenario.bundle_count} {scenario.bundle_count === 1 ? "bundle" : "bundles"}</span></div>
              <div className="scenario-focus">{scenario.focus}</div>
              <div className="scenario-card-action">{active ? <><Check size={14} /> Inspecting</> : <>View details <ChevronRight size={14} /></>}</div>
            </button>;
          })}
          {!scenarios.length && <div className="scenario-empty">No scenario presets are available from the API.</div>}
        </div>

        <aside className="panel scenario-detail-panel">
          {loadingDetails && !selected ? <div className="scenario-loading"><LoaderCircle className="spin" size={18} /> Loading preset…</div> : selected ? <>
            <div className="panel-heading"><div className="heading-icon blue"><Waypoints size={16} /></div><h2>Preset details</h2><span className="section-tag">{selected.orbital_contact_generation ? "LEO" : "FIXED PLAN"}</span></div>
            <div className="scenario-detail-title"><h2>{selected.name}</h2><p>{selected.description}</p></div>
            <div className="scenario-focus-panel"><span>WHAT THIS DEMONSTRATES</span><b>{selected.focus}</b></div>
            <div className="scenario-count-grid"><DetailCount label="Satellites" value={selected.satellite_count} /><DetailCount label="Ground stations" value={selected.ground_station_count} /><DetailCount label="Bundles" value={selected.bundle_count} /><DetailCount label="Contacts" value={selected.orbital_contact_generation ? "Generated" : selected.contact_count} /></div>
            <div className="scenario-detail-section"><div className="scenario-section-title"><Waypoints size={14} /> Network nodes</div>
              <div className="scenario-node-list">{selected.configuration.nodes.map((node) => <div className="scenario-node" key={node.node_id}><span className={`scenario-node-dot ${node.kind}`} /><b>{node.node_id}</b><small>{node.kind === "satellite" ? `${node.orbit?.altitude_km.toFixed(0) ?? "—"} km orbit · ${capacity(node.buffer_capacity_bytes)}` : `Ground station · ${capacity(node.buffer_capacity_bytes)}`}</small></div>)}</div>
            </div>
            <div className="scenario-detail-section"><div className="scenario-section-title"><Clock3 size={14} /> Contact model</div>
              {selected.orbital_contact_generation
                ? <p className="scenario-contact-note">Contact windows are generated from circular-orbit motion, Earth rotation, and line-of-sight visibility when the simulation is created.</p>
                : <div className="scenario-contact-list">{selected.configuration.contacts.map((contact) => <div className="scenario-contact" key={contact.contact_id}><span>{contact.from_node}</span><ArrowDownRight size={13} /><span>{contact.to_node}</span><small>{(contact.start_us / 1_000_000).toFixed(0)}–{(contact.end_us / 1_000_000).toFixed(0)} s</small></div>)}</div>}
            </div>
            <div className="scenario-detail-section"><div className="scenario-section-title"><Layers3 size={14} /> Bundle setup</div>
              {selected.configuration.bundles.map((bundle) => <div className="scenario-bundle" key={bundle.bundle_id}><b>{bundle.bundle_id}</b><span>{bundle.source} → {bundle.destination}</span><small>{(bundle.payload_bytes / 1_000_000).toFixed(2)} MB · TTL {(bundle.ttl_us / 1_000_000).toFixed(0)} s{selected.configuration.bundle_generation_interval_us ? ` · repeat every ${(selected.configuration.bundle_generation_interval_us / 1_000_000).toFixed(0)} s` : ""}</small></div>)}
            </div>
            <button className="primary full-width scenario-load-button" onClick={() => onLoadPreset(selected)} disabled={!canLoadPreset}><Check size={15} /> Use this preset</button>
            {!canLoadPreset && <p className="scenario-disabled-note">Pause the active simulation before loading a preset.</p>}
            <p className="scenario-assumption"><CircleHelp size={13} /> Orbital geometry is a simplified simulator model, not an operational prediction.</p>
          </> : <div className="scenario-empty">Choose a preset to inspect its network and traffic setup.</div>}
        </aside>
      </div>
    </main>
  );
}

function DetailCount({ label, value }: { label: string; value: number | string }) {
  return <div className="scenario-count"><b>{value}</b><span>{label}</span></div>;
}

function capacity(bytes: number) {
  return bytes >= 1_000_000_000
    ? `${(bytes / 1_000_000_000).toFixed(0)} GB buffer`
    : `${(bytes / 1_000_000).toFixed(0)} MB buffer`;
}

export function cloneScenarioConfiguration(configuration: SimulationConfig): SimulationConfig {
  return structuredClone(configuration);
}
