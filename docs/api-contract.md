# Initial API contract (planning)

REST is sufficient for the first dashboard. FastAPI owns request/response validation and invokes a library engine. Commands mutate a run; queries return immutable snapshots. There is no authentication, database, distributed job, or persistence in the initial local version.

## Commands

- `POST /simulations`: create a run from scenario ID or inline validated config, routing policy, and explicit seed; returns run ID and normalized configuration, including the realized satellite/node list and positions. Satellite additions/removals are configuration edits before this command; live topology edits are deferred.
- `POST /simulations/{id}/start`, `/pause`, `/resume`, `/step`, `/reset`: state-changing controls. Step should process one next event in stable queue order and report the resulting snapshot; implement this policy consistently.
- `POST /simulations/{id}/advance`: optional bounded command to advance to a target simulation tick or event count, never wall-clock duration. Include a work limit to prevent unbounded request processing.
- `GET /scenarios`, `GET /scenarios/{id}`: available scenario definitions and detail.

## Queries and exports

- `GET /simulations/{id}`: run state (`ready`, `running`, `paused`, `completed`, `failed`), simulated time, horizon, normalized config, and latest summary.
- `GET /simulations/{id}/nodes`, `/contacts`, `/bundles`: read-only current projections; support selected ID lookup through query/filtering or dedicated detail paths.
- `GET /simulations/{id}/events?after_sequence=N&limit=...`: immutable ordered event records for history and incremental polling.
- `GET /simulations/{id}/metrics`: definitions, values, denominators, cutoff and per-node/per-contact breakdowns.
- `GET /simulations/{id}/export?format=json|csv`: downloadable scenario manifest, events, and experiment outputs.

Commands and queries must not return engine-owned mutable objects. Invalid config produces field-specific validation errors; unknown run/resource is a not-found response; invalid run-state command is a conflict response.

## Minimum dashboard response data

- **Simulation snapshot:** ID, lifecycle state, simulated time/horizon, config/seed, last event sequence, node/contact/bundle counts, summary metrics.
- **Node:** ID, kind, label, configured buffer capacity, current occupancy, scene-frame 3D position when supplied by the scenario. Selected-node detail may include velocity/upcoming contacts only when calculable by the engine/model. Satellite creation/configuration accepts explicit positions or seeded generated placements; normalized simulation configuration returns the resulting IDs and coordinates. These placements do not imply movement or generated contacts.
- **Contact/link:** ID, directed endpoints, start/end, rate, propagation delay, status at snapshot (`planned`, `active`, `inactive`, `completed`), current transmission if any, and observed utilization.
- **Bundle:** ID, source/destination, bytes, creation/expiry ticks, holder or in-flight endpoints, status, and ordered forwarding records including contact, start, serialization completion, receiver acceptance, and successful hop count.
- **Metrics:** value, unit, numerator/denominator where relevant, measured horizon, and metric definition version.

Keep past event history, current projection, and predicted route/contact data separate. Predicted delivery is omitted unless produced by a named routing calculation and labeled with its knowledge assumptions.

## Updates

Initially the frontend polls simulation status/snapshot while a run is active and fetches event pages by sequence cursor. Batch multiple events per response; do not poll once per event. REST snapshots are simpler to debug and test. Add WebSockets only if measured freshness or polling volume warrants it; the engine remains transport-independent.
