# Architecture

## Runtime shape

Use a small monorepo with `backend/` for the Python package and tests, `frontend/` for the Next.js/TypeScript app, and `docs/` plus top-level project documents. Create source modules only when their responsibilities are needed; do not create empty layers to match a diagram. The engine is a Python library within the backend, not an HTTP service of its own.

## Responsibilities and boundaries

| Component | Owns | Must not own |
|---|---|---|
| Domain/model | Node, contact, bundle, event, config value rules | HTTP or rendering state |
| Simulation engine | Simulated clock, deterministic queue, state transitions, transmission lifecycle, snapshots/history | Wall-clock scheduling, API transport, UI logic |
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
3. State transitions append typed, immutable event records. Routing proposes a next hop; the engine verifies resource, contact, expiry, and receiver-buffer constraints before changing state.
4. Queries produce immutable snapshots/DTOs, never references to mutable internal queues or node objects.
5. FastAPI translates user commands into engine operations and snapshots into Pydantic response models.
6. The frontend renders those responses. In the initial REST design it polls status/snapshot while running and requests history/metrics as needed; polling frequency is a UI transport concern, not simulation time.

## Simulation controls and process model

The first local API can hold in-memory runs in one application process. A run's command advances a bounded amount of simulated time or a bounded number of events and returns; it does not require a durable worker. Pause means the API stops issuing advance operations, not that engine time depends on a background wall-clock loop. Step processes one event (or one timestamp batch; contract must choose before API implementation; recommend one event with stable ordering). Reset reconstructs state from the saved normalized config and seed.

Because initial state is in memory, restart loses runs. Do not imply persistence. If continuous run commands later block request handling, add a narrowly scoped local task mechanism only after measurement; do not preemptively add a broker.

## Visualization data requirements

The globe/map/topology needs node identifiers/types and model-supported positions; contact endpoints, scheduled interval, rate, and current active state; simulated time; bundle source/destination/current holder/status; and forwarding events with timestamps. The right panel needs selected node details (including velocity/upcoming contacts only if the engine model supports them), selected bundle metadata and event path, and summary metrics. Provide current state, historical event data, and computed future contacts as distinct fields/labels. Never show estimated delivery time unless a routing calculation returns one with its assumptions.

The mockup's left configuration panel, central dominant visualization and playback timeline, and right bundle/network/node detail panels map to independent frontend components: `SimulationSetup`, `SatelliteConfiguration`, `AdvancedParameters`, `NetworkViewport` with view selector/legend, `PlaybackControls`, `BundleDetails`, `NetworkStatus`, and `NodeDetails`. Shared selection and API query state belong at the dashboard/page boundary. `SatelliteConfiguration` must support presets and custom counts, adding/removing satellites, explicit 3D placements, and seeded random placement. Rendering and selection must use the returned node collection rather than a fixed set of satellite slots; the mockup's 72-satellite example is not a cap. Keep a benchmarked practical limit in the eventual UI based on laptop performance rather than claiming unlimited scale. This is a conceptual decomposition, not a demand to create each file immediately.

The Earth is stationary in the scene coordinate system and must not spin automatically. Users can rotate the camera/view around it. With packet-follow enabled for a selected bundle, the viewport adjusts camera orientation/target so the bundle remains in view as it moves between nodes; this is a view transform and must not mutate Earth or satellite state. A visible toggle/exit control returns manual camera control. During a real transmission, a packet marker may be interpolated along the engine-reported active contact using its start/completion time and simulated time. While stored, it remains at its current holder. Never animate across an unavailable contact or invent packet progress. At playback stops, derive marker position from the current simulation snapshot, not wall-clock animation.

## Visualization and update trade-offs

The reference suggests globe, 2D map, and topology modes. Choose a rendering library only after comparing projection/orbit support, node/link scale, selection/accessibility, bundle-path rendering, licensing, bundle size, and laptop performance. A topology view is sufficient for the first functional UI. 3D orbital positions are deferred until a contact/position model supplies truthful data. REST polling is simplest initially; batch snapshots/history since a cursor or simulation time. Consider WebSockets only if measured polling latency/volume makes it useful. The engine emits events/snapshots independent of either transport.

For dynamic constellation setup, the API accepts a normalized scenario containing the selected satellite nodes and placements; the frontend edits this configuration before creating a run. Seeded random generation must be reproducible and the server returns the realized node list. The first version does not mutate a running topology. During playback, the frontend may interpolate a bundle glyph only over an engine-reported active transmission and must keep it at the holder while queued. Packet-follow changes only the view camera/target; it does not rotate the Earth model or change simulation coordinates.

## Testability

Import and run the engine directly in pytest. Keep routing decisions as pure-ish policy calls over explicit state, event scheduling deterministic, and metrics pure over recorded results. Test API translation separately from engine behavior and frontend rendering against response fixtures. Never require a server to verify core network semantics.
