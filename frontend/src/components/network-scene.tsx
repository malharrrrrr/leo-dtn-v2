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
    let packetMarker: THREE.Mesh | null = null;
    const contactLines = new Map<string, THREE.Line>();
    const contactArrows = new Map<string, THREE.Mesh>();
    const render = () => {
      frame = requestAnimationFrame(render);
      const data = stateRef.current;
      const selectedBundle = data.snapshot?.bundles.find((bundle) => bundle.bundle_id === data.selectedBundleId);
      let nextTopologySignature = topologySignature;
      if (data.snapshot !== lastSnapshot || data.selectedBundleId !== lastBundleId) {
        lastSnapshot = data.snapshot;
        nextTopologySignature = data.snapshot ? JSON.stringify({
          nodes: data.snapshot.nodes.map((node) => [node.node_id, node.kind, node.position_km]),
          contacts: data.snapshot.contacts.map((contact) => [contact.contact_id, contact.from_node, contact.to_node]),
          bundlePath: selectedBundle?.forwarding_history.map((hop) => hop.contact_id) ?? [],
          hasBundle: Boolean(selectedBundle),
        }) : "";
      }

      if (nextTopologySignature !== topologySignature || data.selectedBundleId !== lastBundleId) {
        for (const child of [...network.children]) {
          network.remove(child);
          if (child instanceof THREE.Mesh || child instanceof THREE.Line) {
            child.geometry.dispose();
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            materials.forEach((material) => material.dispose());
          }
        }
        contactLines.clear();
        contactArrows.clear();
        packetMarker = null;
        topologySignature = nextTopologySignature;
        lastBundleId = data.selectedBundleId;

        if (data.snapshot) {
          const positions = new Map<string, THREE.Vector3>();
          for (const node of data.snapshot.nodes) {
            const position = toScene(node.position_km, node.node_id, node.kind);
            positions.set(node.node_id, position);
            const geometry = node.kind === "satellite"
              ? new THREE.OctahedronGeometry(0.055, 0)
              : new THREE.SphereGeometry(0.032, 16, 16);
            const material = new THREE.MeshStandardMaterial({
              color: node.kind === "satellite" ? "#57b8ff" : "#e8fcff",
              emissive: node.kind === "satellite" ? "#075a9b" : "#26a4a0",
              emissiveIntensity: 0.6,
            });
            const marker = new THREE.Mesh(geometry, material);
            marker.position.copy(position); marker.userData.nodeId = node.node_id;
            network.add(marker);
            const glow = new THREE.Mesh(new THREE.SphereGeometry(0.09, 12, 12), new THREE.MeshBasicMaterial({ color: node.kind === "satellite" ? 0x1689db : 0x20d6b1, transparent: true, opacity: 0.14 }));
            glow.position.copy(position); glow.userData.nodeId = node.node_id; network.add(glow);
          }

          for (const contact of data.snapshot.contacts) {
            const from = positions.get(contact.from_node); const to = positions.get(contact.to_node);
            if (!from || !to) continue;
            const line = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints([from, to]),
              new THREE.LineBasicMaterial({ color: 0x4c5663, transparent: true, opacity: 0.34 }),
            );
            contactLines.set(contact.contact_id, line);
            network.add(line);
            const arrow = new THREE.Mesh(
              new THREE.ConeGeometry(0.022, 0.075, 8),
              new THREE.MeshBasicMaterial({ color: 0x4c5663, transparent: true, opacity: 0.8 }),
            );
            arrow.position.copy(from).lerp(to, 0.72);
            arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize());
            contactArrows.set(contact.contact_id, arrow);
            network.add(arrow);
          }

          for (const hop of selectedBundle?.forwarding_history ?? []) {
            const from = positions.get(hop.from_node); const to = positions.get(hop.to_node);
            if (!from || !to) continue;
            const path = new THREE.Line(
              new THREE.BufferGeometry().setFromPoints([from, to]),
              new THREE.LineBasicMaterial({ color: 0xffb547, transparent: true, opacity: 0.95 }),
            );
            network.add(path);
          }

          if (selectedBundle) {
            packetMarker = new THREE.Mesh(
              new THREE.SphereGeometry(0.035, 16, 16),
              new THREE.MeshBasicMaterial({ color: selectedBundle.status === "delivered" ? 0x4ff2a4 : 0xffb547 }),
            );
            network.add(packetMarker);
          }
        }
      }

      if (data.snapshot) {
        for (const contact of data.snapshot.contacts) {
          const line = contactLines.get(contact.contact_id);
          if (!line) continue;
          const material = line.material as THREE.LineBasicMaterial;
          const contactColor = contact.status === "active" ? 0x16d6a1 : contact.status === "planned" ? 0x2889cb : 0x4c5663;
          material.color.set(contactColor);
          material.opacity = contact.status === "active" ? 0.85 : 0.34;
          const arrow = contactArrows.get(contact.contact_id);
          if (arrow) (arrow.material as THREE.MeshBasicMaterial).color.set(contactColor);
        }
        const packet = bundlePosition(selectedBundle, data.snapshot);
        if (packet && packetMarker) {
          packetMarker.position.copy(packet);
          (packetMarker.material as THREE.MeshBasicMaterial).color.set(selectedBundle?.status === "delivered" ? 0x4ff2a4 : 0xffb547);
          if (data.followPacket) controls.target.lerp(packet, 0.09);
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
