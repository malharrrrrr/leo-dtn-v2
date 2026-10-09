"use client";

import type { SimulationSnapshot } from "@/lib/contracts";

type Props = {
  snapshot: SimulationSnapshot | null;
  selectedBundleId: string | null;
  onSelectNode: (nodeId: string) => void;
};

export function NetworkTopology({ snapshot, selectedBundleId, onSelectNode }: Props) {
  if (!snapshot) return <div className="topology-empty">Create a simulation to view its configured topology.</div>;
  const center = { x: 400, y: 286 };
  const radius = Math.min(215, 60 + snapshot.nodes.length * 12);
  const positions = new Map(snapshot.nodes.map((node, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / Math.max(snapshot.nodes.length, 1);
    return [node.node_id, snapshot.nodes.length === 1
      ? center
      : { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius }] as const;
  }));
  const bundle = snapshot.bundles.find((item) => item.bundle_id === selectedBundleId);
  const usedContacts = new Set(bundle?.forwarding_history.map((hop) => hop.contact_id) ?? []);

  return (
    <svg className="topology-view" viewBox="0 0 800 600" role="img" aria-label="Configured network topology">
      <defs>
        <pattern id="topology-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="#203044" strokeWidth=".7" opacity=".6" /></pattern>
        <marker id="contact-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M 0 0 L 8 4 L 0 8 z" fill="#91a3b7" /></marker>
      </defs>
      <rect width="800" height="600" fill="url(#topology-grid)" />
      {snapshot.contacts.map((contact) => {
        const from = positions.get(contact.from_node); const to = positions.get(contact.to_node);
        if (!from || !to) return null;
        const path = usedContacts.has(contact.contact_id);
        const stroke = path ? "#ffb547" : contact.status === "active" ? "#20d6a1" : contact.status === "planned" ? "#298dca" : "#455568";
        return <g key={contact.contact_id}>
          <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={stroke} strokeWidth={path ? 3 : 1.5} strokeDasharray={contact.status === "planned" ? "7 6" : undefined} markerEnd="url(#contact-arrow)" opacity={contact.status === "completed" ? .42 : .88} />
          <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8} textAnchor="middle" className="topology-contact-label">{contact.contact_id}</text>
        </g>;
      })}
      {snapshot.nodes.map((node) => {
        const position = positions.get(node.node_id)!;
        const ground = node.kind === "ground_station";
        return <g key={node.node_id} className="topology-node" onClick={() => onSelectNode(node.node_id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelectNode(node.node_id); }} role="button" tabIndex={0} aria-label={`Select ${node.node_id}`}>
          {ground ? <circle cx={position.x} cy={position.y} r="19" fill="#132f3e" stroke="#59c8cf" strokeWidth="2" /> : <polygon points={`${position.x},${position.y - 22} ${position.x + 18},${position.y - 7} ${position.x + 12},${position.y + 17} ${position.x - 12},${position.y + 17} ${position.x - 18},${position.y - 7}`} fill="#10345a" stroke="#56b3ff" strokeWidth="2" />}
          <circle cx={position.x} cy={position.y} r="5" fill={ground ? "#b8ffff" : "#76caff"} />
          <text x={position.x} y={position.y + 37} textAnchor="middle" className="topology-node-label">{node.node_id}</text>
          <text x={position.x} y={position.y + 51} textAnchor="middle" className="topology-kind-label">{ground ? "GROUND STATION" : "SATELLITE"}</text>
        </g>;
      })}
      <text x="18" y="28" className="topology-caption">CURRENT ENGINE CONTACT PLAN · t = {(snapshot.time_us / 1_000_000).toFixed(2)} s</text>
    </svg>
  );
}
