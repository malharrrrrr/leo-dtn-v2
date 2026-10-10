"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { BundleState, NodeState, SimulationSnapshot } from "@/lib/contracts";

type Props = {
  snapshot: SimulationSnapshot | null;
  selectedBundleId: string | null;
  followPacket: boolean;
  onSelectNode: (nodeId: string) => void;
};

const EARTH_RADIUS_KM = 6371;
const FALLBACK_STATIONS: Record<string, [number, number, number]> = {
  "GS-A": [EARTH_RADIUS_KM, 0, 0],
  "GS-B": [0, 0, -EARTH_RADIUS_KM],
};

function toScene(position: [number, number, number] | null, nodeId: string, kind: NodeState["kind"]): THREE.Vector3 {
  const coordinates = position ?? FALLBACK_STATIONS[nodeId] ?? (kind === "ground_station" ? [0, EARTH_RADIUS_KM, 0] : [0, 0, EARTH_RADIUS_KM * 1.14]);
  const vector = new THREE.Vector3(...coordinates).multiplyScalar(1 / EARTH_RADIUS_KM);
  if (kind === "ground_station") vector.setLength(1.012);
  return vector;
}

function makeEarthTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 2048;
  canvas.height = 1024;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas texture is unavailable");
  const ocean = context.createLinearGradient(0, 0, 0, 1024);
  ocean.addColorStop(0, "#123b62");
  ocean.addColorStop(0.5, "#0e4b73");
  ocean.addColorStop(1, "#122f51");
  context.fillStyle = ocean;
  context.fillRect(0, 0, 2048, 1024);

  context.strokeStyle = "rgba(119, 207, 241, 0.17)";
  context.lineWidth = 2;
  for (let longitude = 0; longitude <= 2048; longitude += 128) {
    context.beginPath(); context.moveTo(longitude, 0); context.lineTo(longitude, 1024); context.stroke();
  }
  for (let latitude = 0; latitude <= 1024; latitude += 128) {
    context.beginPath(); context.moveTo(0, latitude); context.lineTo(2048, latitude); context.stroke();
  }

  const continents = [
    [[150, 220], [260, 160], [390, 195], [460, 280], [390, 350], [350, 455], [260, 450], [200, 360]],
    [[430, 485], [520, 520], [555, 625], [510, 795], [445, 735], [405, 600]],
    [[900, 230], [1010, 190], [1090, 255], [1050, 345], [985, 390], [945, 340]],
    [[1000, 390], [1125, 405], [1180, 515], [1130, 710], [1050, 775], [1000, 610], [955, 505]],
    [[1080, 220], [1250, 150], [1450, 205], [1570, 300], [1460, 390], [1330, 355], [1230, 305]],
    [[1370, 555], [1535, 535], [1635, 625], [1570, 720], [1430, 690]],
    [[1700, 300], [1790, 345], [1840, 430], [1780, 520], [1700, 460]],
  ];
  context.fillStyle = "#3f806d";
  context.strokeStyle = "#7eb58c";
  context.lineWidth = 5;
  continents.forEach((polygon) => {
    context.beginPath();
    polygon.forEach(([x, y], index) => index ? context.lineTo(x, y) : context.moveTo(x, y));
    context.closePath(); context.fill(); context.stroke();
  });
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function bundlePosition(bundle: BundleState | undefined, snapshot: SimulationSnapshot): THREE.Vector3 | null {
  if (!bundle) return null;
  const active = snapshot.active_transmissions.find((item) => item.bundle_id === bundle.bundle_id);
  if (active) {
    const from = snapshot.nodes.find((node) => node.node_id === active.from_node);
    const to = snapshot.nodes.find((node) => node.node_id === active.to_node);
    if (from && to) {
      const start = toScene(from.position_km, from.node_id, from.kind);
      const end = toScene(to.position_km, to.node_id, to.kind);
      const span = active.serialization_complete_us - active.start_time_us;
      const progress = span <= 0 ? 1 : THREE.MathUtils.clamp((snapshot.time_us - active.start_time_us) / span, 0, 1);
      return start.lerp(end, progress);
    }
  }
  if (bundle.holder) {
    const holder = snapshot.nodes.find((node) => node.node_id === bundle.holder);
    if (holder) return toScene(holder.position_km, holder.node_id, holder.kind);
  }
  const lastHop = bundle.forwarding_history.at(-1);
  if (lastHop) {
    const receiver = snapshot.nodes.find((node) => node.node_id === lastHop.to_node);
    if (receiver) return toScene(receiver.position_km, receiver.node_id, receiver.kind);
  }
  const source = snapshot.nodes.find((node) => node.node_id === bundle.source);
  return source ? toScene(source.position_km, source.node_id, source.kind) : null;
}

function addPickTag(object: THREE.Object3D, nodeId: string) {
  object.userData.nodeId = nodeId;
  object.traverse((child) => { child.userData.nodeId = nodeId; });
}

function satelliteGlyph(nodeId: string): THREE.Group {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.052, 0.052), new THREE.MeshStandardMaterial({ color: 0xd9eaff, emissive: 0x327cb5, emissiveIntensity: 0.75, metalness: 0.7, roughness: 0.3 }));
  group.add(body);
  for (const side of [-1, 1]) {
    const panel = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.014, 0.075), new THREE.MeshStandardMaterial({ color: 0x197fd0, emissive: 0x063d75, emissiveIntensity: 0.8, metalness: 0.55, roughness: 0.4 }));
    panel.position.x = side * 0.105; group.add(panel);
    const cell = new THREE.LineSegments(new THREE.EdgesGeometry(panel.geometry), new THREE.LineBasicMaterial({ color: 0x8bd4ff }));
    cell.position.copy(panel.position); group.add(cell);
  }
  const antenna = new THREE.Mesh(new THREE.SphereGeometry(0.02, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0xffe9b0 }));
  antenna.position.y = 0.027; group.add(antenna);
  const halo = new THREE.Mesh(new THREE.SphereGeometry(0.09, 12, 12), new THREE.MeshBasicMaterial({ color: 0x1689db, transparent: true, opacity: 0.12, depthWrite: false }));
  group.add(halo); addPickTag(group, nodeId);
  return group;
}

function stationGlyph(nodeId: string): THREE.Group {
  const group = new THREE.Group();
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.007, 0.012, 0.08, 8), new THREE.MeshStandardMaterial({ color: 0xd6e5ee, emissive: 0x247e85, emissiveIntensity: 0.4 }));
  mast.position.y = 0.03; group.add(mast);
  const dish = new THREE.Mesh(new THREE.SphereGeometry(0.05, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0xe5f4fa, emissive: 0x137b82, emissiveIntensity: 0.45, side: THREE.DoubleSide }));
  dish.rotation.x = -Math.PI / 3; dish.position.y = 0.07; group.add(dish);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.052, 0.018, 14), new THREE.MeshStandardMaterial({ color: 0x32c7bc, emissive: 0x06605d, emissiveIntensity: 0.5 }));
  group.add(base); addPickTag(group, nodeId);
  return group;
}

function clearsEarth(a: THREE.Vector3, b: THREE.Vector3): boolean {
  const ab = b.clone().sub(a); const t = THREE.MathUtils.clamp(-a.dot(ab) / ab.lengthSq(), 0, 1);
  return a.clone().addScaledVector(ab, t).lengthSq() >= 1.001 * 1.001;
}

export function NetworkScene({ snapshot, selectedBundleId, followPacket, onSelectNode }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef({ snapshot, selectedBundleId, followPacket, onSelectNode });
  stateRef.current = { snapshot, selectedBundleId, followPacket, onSelectNode };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#050b14");
    const camera = new THREE.PerspectiveCamera(42, host.clientWidth / host.clientHeight, 0.1, 100);
    camera.position.set(0, 0.25, 3.4);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8));
    renderer.setSize(host.clientWidth, host.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    host.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = false;
    controls.minDistance = 1.5;
    controls.maxDistance = 8;

    scene.add(new THREE.AmbientLight(0x8cb6d8, 1.4));
    const sun = new THREE.DirectionalLight(0xe4f3ff, 3.1);
    sun.position.set(-3, 2, 4); scene.add(sun);

    const earth = new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 64),
      new THREE.MeshStandardMaterial({ map: makeEarthTexture(), roughness: 0.96, metalness: 0.02 }),
    );
    earth.position.set(0, 0, 0);
    scene.add(earth);
    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(1.025, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x238bd6, transparent: true, opacity: 0.09, side: THREE.BackSide }),
    );
    scene.add(atmosphere);

    const starPositions = new Float32Array(900 * 3);
    for (let i = 0; i < 900; i++) {
      const radius = 5 + Math.random() * 22;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      starPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      starPositions[i * 3 + 1] = radius * Math.cos(phi);
      starPositions[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    }
    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute("position", new THREE.Float32BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0xb5cce0, size: 0.012, transparent: true, opacity: 0.7 }));
    scene.add(stars);

    const network = new THREE.Group(); scene.add(network);
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const onPointerDown = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(network.children, true).find((item) => item.object.userData.nodeId);
      if (hit?.object.userData.nodeId) stateRef.current.onSelectNode(hit.object.userData.nodeId as string);
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);

    const observer = new ResizeObserver(() => {
      if (!host.clientWidth || !host.clientHeight) return;
      camera.aspect = host.clientWidth / host.clientHeight; camera.updateProjectionMatrix();
      renderer.setSize(host.clientWidth, host.clientHeight);
    });
    observer.observe(host);

    let frame = 0;
    let lastSnapshot: SimulationSnapshot | null = null;
    let topologySignature = "";
    let lastBundleId: string | null = null;
    let packetMarker: THREE.Group | null = null;
    const contactLines = new Map<string, THREE.Mesh>();
    const contactArrows = new Map<string, THREE.Mesh>();
    const nodeGlyphs = new Map<string, THREE.Group>();
    const satelliteTrails = new Map<string, { line: THREE.Line; points: THREE.Vector3[] }>();
    const pathLines: THREE.Line[] = [];
    let packetTrail: THREE.Line | null = null;
    let lastTrailTime = -1;
    const render = () => {
      frame = requestAnimationFrame(render);
      const data = stateRef.current;
      const selectedBundle = data.snapshot?.bundles.find((bundle) => bundle.bundle_id === data.selectedBundleId);
      let nextTopologySignature = topologySignature;
      if (data.snapshot !== lastSnapshot || data.selectedBundleId !== lastBundleId) {
        lastSnapshot = data.snapshot;
        nextTopologySignature = data.snapshot ? JSON.stringify({
          nodes: data.snapshot.nodes.map((node) => [node.node_id, node.kind, node.orbit]),
          contacts: data.snapshot.contacts.map((contact) => [contact.contact_id, contact.from_node, contact.to_node]),
          bundlePath: selectedBundle?.forwarding_history.map((hop) => hop.contact_id) ?? [],
          hasBundle: Boolean(selectedBundle),
        }) : "";
      }

      if (nextTopologySignature !== topologySignature || data.selectedBundleId !== lastBundleId) {
        for (const child of [...network.children]) {
          network.remove(child);
          child.traverse((object) => {
            if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
              object.geometry.dispose();
              const materials = Array.isArray(object.material) ? object.material : [object.material];
              materials.forEach((material) => material.dispose());
            }
          });
        }
        contactLines.clear();
        contactArrows.clear();
        nodeGlyphs.clear(); satelliteTrails.clear(); pathLines.length = 0; packetTrail = null; lastTrailTime = -1;
        packetMarker = null;
        topologySignature = nextTopologySignature;
        lastBundleId = data.selectedBundleId;

        if (data.snapshot) {
          const positions = new Map<string, THREE.Vector3>();
          for (const node of data.snapshot.nodes) {
            const position = toScene(node.position_km, node.node_id, node.kind);
            positions.set(node.node_id, position);
            const glyph = node.kind === "satellite" ? satelliteGlyph(node.node_id) : stationGlyph(node.node_id);
            glyph.position.copy(position); nodeGlyphs.set(node.node_id, glyph); network.add(glyph);
            if (node.kind === "satellite") {
              const trail = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x42c9ff, transparent: true, opacity: 0.82, depthWrite: false }));
              trail.visible = false;
              network.add(trail); satelliteTrails.set(node.node_id, { line: trail, points: [] });
            }
          }

          for (const contact of data.snapshot.contacts) {
            const from = positions.get(contact.from_node); const to = positions.get(contact.to_node);
            if (!from || !to) continue;
            const line = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 1, 7), new THREE.MeshBasicMaterial({ color: 0x4c5663, transparent: true, opacity: 0.34, depthWrite: false }));
            contactLines.set(contact.contact_id, line);
            network.add(line);
            const arrow = new THREE.Mesh(
              new THREE.ConeGeometry(0.025, 0.09, 8),
              new THREE.MeshBasicMaterial({ color: 0x4c5663, transparent: true, opacity: 0.8 }),
            );
            arrow.position.copy(from).lerp(to, 0.72);
            arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize());
            contactArrows.set(contact.contact_id, arrow);
            network.add(arrow);
          }

          for (const hop of selectedBundle?.forwarding_history ?? []) {
            const fromNode = data.snapshot.nodes.find((node) => node.node_id === hop.from_node);
            const toNode = data.snapshot.nodes.find((node) => node.node_id === hop.to_node);
            const from = hop.from_position_km && fromNode ? toScene(hop.from_position_km, fromNode.node_id, fromNode.kind) : positions.get(hop.from_node);
            const to = hop.to_position_km && toNode ? toScene(hop.to_position_km, toNode.node_id, toNode.kind) : positions.get(hop.to_node);
            if (!from || !to) continue;
            const path = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints([from, to]),
              new THREE.LineBasicMaterial({ color: 0xffb547, transparent: true, opacity: 0.95 }),
            );
            network.add(path); pathLines.push(path);
          }

          if (selectedBundle) {
            packetMarker = new THREE.Group();
            const packetColor = selectedBundle.status === "delivered" ? 0x4ff2a4 : 0xffb547;
            const core = new THREE.Mesh(new THREE.OctahedronGeometry(0.065, 1), new THREE.MeshBasicMaterial({ color: packetColor }));
            core.renderOrder = 10; packetMarker.add(core);
            const ring = new THREE.Mesh(new THREE.TorusGeometry(0.105, 0.009, 8, 28), new THREE.MeshBasicMaterial({ color: packetColor, depthWrite: false }));
            ring.rotation.x = Math.PI / 2; ring.renderOrder = 9; packetMarker.add(ring);
            const glow = new THREE.Mesh(new THREE.SphereGeometry(0.13, 16, 12), new THREE.MeshBasicMaterial({ color: packetColor, transparent: true, opacity: 0.17, depthWrite: false }));
            glow.name = "packet-glow"; glow.renderOrder = 8; packetMarker.add(glow);
            network.add(packetMarker);
            packetTrail = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: 0xffd166, dashSize: 0.035, gapSize: 0.02, transparent: true, opacity: 0.95 }));
            packetTrail.renderOrder = 8; network.add(packetTrail);
          }
        }
      }

      if (data.snapshot) {
        const positions = new Map<string, THREE.Vector3>();
        for (const node of data.snapshot.nodes) {
          const position = toScene(node.position_km, node.node_id, node.kind); positions.set(node.node_id, position);
          const glyph = nodeGlyphs.get(node.node_id);
          if (glyph) {
            glyph.position.copy(position);
            if (node.kind === "ground_station") glyph.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), position.clone().normalize());
            else if (node.velocity_km_s) glyph.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), new THREE.Vector3(...node.velocity_km_s).normalize());
            const farSide = position.dot(camera.position) < 0;
            glyph.traverse((part) => {
              if (!(part instanceof THREE.Mesh || part instanceof THREE.LineSegments)) return;
              const materials = Array.isArray(part.material) ? part.material : [part.material];
              materials.forEach((material) => {
                if (material.userData.savedOpacity === undefined) {
                  material.userData.savedOpacity = material.opacity;
                  material.userData.savedTransparent = material.transparent;
                }
                material.depthTest = !farSide;
                material.transparent = farSide || material.userData.savedTransparent;
                material.opacity = material.userData.savedOpacity * (farSide ? 0.42 : 1);
              });
            });
          }
          const trail = satelliteTrails.get(node.node_id);
          if (trail && data.snapshot.time_us !== lastTrailTime) {
            trail.points.push(position.clone());
            if (trail.points.length > 400) trail.points.shift();
            if (trail.points.length >= 2) {
              trail.line.geometry.setFromPoints(trail.points);
              trail.line.visible = true;
            }
          }
        }
        if (data.snapshot.time_us !== lastTrailTime) lastTrailTime = data.snapshot.time_us;
        for (const contact of data.snapshot.contacts) {
          const line = contactLines.get(contact.contact_id);
          if (!line) continue;
          const from = positions.get(contact.from_node); const to = positions.get(contact.to_node);
          if (from && to) {
            line.visible = clearsEarth(from, to) && (contact.status === "active" || contact.status === "planned");
            const direction = to.clone().sub(from);
            line.position.copy(from).add(to).multiplyScalar(0.5);
            line.scale.set(contact.status === "active" ? 0.0055 : 0.0028, direction.length(), contact.status === "active" ? 0.0055 : 0.0028);
            line.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
            const arrow = contactArrows.get(contact.contact_id);
            if (arrow) {
              arrow.position.copy(from).lerp(to, 0.75);
              arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize());
              arrow.visible = line.visible;
            }
          }
          const material = line.material as THREE.MeshBasicMaterial;
          const contactColor = contact.status === "active" ? 0x16d6a1 : contact.status === "planned" ? 0x2889cb : 0x4c5663;
          material.color.set(contactColor);
          material.opacity = contact.status === "active" ? 0.85 : 0.34;
          const arrow = contactArrows.get(contact.contact_id);
          if (arrow) (arrow.material as THREE.MeshBasicMaterial).color.set(contactColor);
        }
        const packet = bundlePosition(selectedBundle, data.snapshot);
        if (packet && packetMarker) {
          packetMarker.position.copy(packet);
          const packetColor = selectedBundle?.status === "delivered" ? 0x4ff2a4 : 0xffb547;
          packetMarker.children.forEach((part) => {
            if (part instanceof THREE.Mesh && part.material instanceof THREE.MeshBasicMaterial) part.material.color.set(packetColor);
          });
          if (data.followPacket) {
            // Keep Earth fixed in simulation space and move the camera frame to the
            // engine-reported bundle position. This brings far-side bundle traffic
            // into view without rotating the globe or inventing packet motion.
            const range = Math.max(1.8, camera.position.distanceTo(controls.target));
            controls.target.copy(packet);
            camera.position.copy(packet.clone().normalize().multiplyScalar(packet.length() + range));
          }
          const active = data.snapshot.active_transmissions.find((item) => item.bundle_id === selectedBundle?.bundle_id);
          const sender = active && positions.get(active.from_node);
          if (packetTrail && sender && active) {
            packetTrail.geometry.setFromPoints([sender, packet]);
            packetTrail.computeLineDistances(); packetTrail.visible = true;
          } else if (packetTrail) packetTrail.visible = false;
        }
      }
      if (!data.followPacket) controls.target.lerp(new THREE.Vector3(0, 0, 0), 0.04);
      controls.update();
      renderer.render(scene, camera);
    };
    render();

    return () => {
      cancelAnimationFrame(frame); observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      controls.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => {
            if ("map" in material && material.map instanceof THREE.Texture) material.map.dispose();
            material.dispose();
          });
        }
      });
      renderer.dispose(); renderer.domElement.remove();
    };
  }, []);

  return <div className="scene-host" ref={hostRef} aria-label="Interactive three-dimensional network visualization" />;
}
