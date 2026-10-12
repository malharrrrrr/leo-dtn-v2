# Architecture

## Runtime shape

Use a small monorepo with `backend/` for the Python package and tests, `frontend/` for the Next.js/TypeScript app, and `docs/` plus top-level project documents. Create source modules only when their responsibilities are needed; do not create empty layers to match a diagram. The engine is a Python library within the backend, not an HTTP service of its own.

## Responsibilities and boundaries

| Component | Owns | Must not own |
|---|---|---|
| Domain/model | Node, orbit, contact, bundle, event, config value rules | HTTP or rendering state |
| Simulation engine | Simulated clock, deterministic queue, circular-orbit propagation, geometry-derived contact plan, state transitions, transmission lifecycle, snapshots/history | Wall-clock scheduling, API transport, UI logic |
| Routing policy | Candidate next-hop decision from current state and declared contact knowledge | Event execution, buffer mutation, delivery claims |
| Scenario/experiment layer | Validated configuration, seeded generation, run manifest and result aggregation | Hidden random state or alternate forwarding semantics |
| FastAPI adapter | Pydantic validation, run control, query/export endpoints, engine invocation | Routing/contact/expiry rules |
| Frontend | Controls, visualization, selection, presentation and polling | Independent simulation state or prediction not supplied by engine |

Avoid premature generic plugin systems. The routing interface and event records are the first extension seams; split packages further only when actual code needs the boundary.

## First vertical slice components

Only a clock/event queue, compact domain models, precomputed contacts, one bundle lifecycle, one forwarding policy, immutable snapshots/history, and a scenario fixture are needed. FastAPI and frontend are deliberately absent from this milestone. Metrics can be small pure aggregation functions after core events are reliable.

## State and data flow

1. A validated scenario/configuration and explicit seed enter the engine.
2. The engine schedules initial events and advances simulated time only by popping events.
3. State transitions append typed, immutable event records. The engine propagates satellite states at simulated time. In orbital mode, the session generates geometry-based contacts through each configured bundle's expiry and keeps a rolling lookahead at least as long as the maximum configured TTL. Routing proposes a next hop from that known plan, and the engine verifies resource, contact, expiry, and receiver-buffer constraints before changing state.
4. Queries produce immutable snapshots/DTOs, never references to mutable internal queues or node objects.
5. FastAPI translates user commands into engine operations and snapshots into Pydantic response models.
6. The frontend renders those responses. In the initial REST design it polls status/snapshot while running and requests history/metrics as needed; polling frequency is a UI transport concern, not simulation time.

## Simulation controls and process model

The local API holds in-memory runs in one application process. Orbital sessions use a small API-owned playback task to request bounded engine advances at a fixed pace; the engine itself remains wall-clock independent. This allows continuous orbital playback while the API is on, even if the dashboard is closed. Pause stops advancement, and API shutdown loses the in-memory run and cancels its tasks. Explicit-contact runs remain command-driven. Step processes one event with stable ordering. Reset reconstructs state from the saved normalized config and seed.

Because initial state is in memory, restart loses runs. Do not imply persistence. If continuous run commands later block request handling, add a narrowly scoped local task mechanism only after measurement; do not preemptively add a broker.

## Visualization data requirements

The globe/map/topology needs node identifiers/types and model-supported positions/velocities at simulated time; contact endpoints, scheduled interval, rate, and current active state; simulated time; bundle source/destination/current holder/status; and forwarding events with timestamps. The right panel needs selected node details, upcoming generated contact windows, selected bundle metadata and event path, and summary metrics. Provide current state, historical event data, and computed future contacts as distinct fields/labels. Never show estimated delivery time unless a routing calculation returns one with its assumptions.

The mockup's left configuration panel, central dominant visualization and playback timeline, and right bundle/network/node detail panels map to independent frontend components: `SimulationSetup`, `SatelliteConfiguration`, `AdvancedParameters`, `NetworkViewport` with view selector/legend, `PlaybackControls`, `BundleDetails`, `NetworkStatus`, and `NodeDetails`. A separate Scenarios view uses the backend preset catalog and detail configuration; selecting “Use this preset” changes only the next-run configuration, not an active engine. Shared selection and API query state belong at the dashboard/page boundary. `SatelliteConfiguration` supports custom counts, adding/removing satellites, explicit 3D placements, and seeded random placement; presets are a separate entry path. Rendering and selection must use the returned node collection rather than a fixed set of satellite slots; the mockup's 72-satellite example is not a cap. Keep a benchmarked practical limit in the eventual UI based on laptop performance rather than claiming unlimited scale. This is a conceptual decomposition, not a demand to create each file immediately.

The Earth is stationary in the scene coordinate system and must not spin automatically. The engine returns moving Earth-fixed satellite positions and velocities as simulated time advances; the frontend must draw those returned states without calculating its own orbit. Users can rotate the camera/view around the Earth. With packet-follow enabled for a selected bundle, the viewport follows its engine-reported position; this changes only the camera/view and never rotates the Earth. During a real transmission, a packet marker is interpolated along the engine-reported active line-of-sight contact using its start/completion time and simulated time. While stored, it remains at its current holder. Never animate across an unavailable contact or invent packet progress. At playback stops, derive marker position from the current simulation snapshot, not wall-clock animation.

## Visualization and update trade-offs

The current 3D view uses Three.js and the topology view uses SVG. A geographic 2D map requires explicit latitude/longitude semantics and is not enabled for raw XYZ inputs. REST polling is simplest initially; short bounded simulation-time advances expose transmission progress without tying the engine to rendering. Consider WebSockets only if measured polling latency/volume makes it useful. The engine emits events/snapshots independent of either transport.

For dynamic constellation setup, the API accepts a normalized scenario containing the selected satellite nodes and circular orbital elements; the frontend edits this configuration before creating a run. Seeded random generation must be reproducible and the server returns the realized node list. In orbital mode, the submitted horizon is a minimum; the session initially plans through configured bundle expiry and maintains TTL-sized future contact coverage for recurring traffic. Generated contacts use the same contact interface and transmission lifecycle as explicit schedules. The first version does not mutate a running topology. During playback, the frontend may interpolate a bundle glyph only over an engine-reported active transmission and must keep it at the holder while queued. Packet-follow changes only the view camera/target; it does not rotate the Earth model or change simulation coordinates.

## Testability

Import and run the engine directly in pytest. Keep routing decisions as pure-ish policy calls over explicit state, event scheduling deterministic, and metrics pure over recorded results. Test API translation separately from engine behavior and frontend rendering against response fixtures. Never require a server to verify core network semantics.
