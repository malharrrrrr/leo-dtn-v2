# API contract

The REST layer is an adapter around the Python engine. Pydantic validates inputs and shapes outputs; it does not implement routing, contact selection, or bundle transitions. Runs live in memory for the lifetime of one API process. Restarting the process loses them.

## Commands

| Method and path | Purpose |
|---|---|
| `POST /simulations` | Create from one registered `scenario_id` or an inline `configuration`, plus required `random_seed`, `horizon_us`, and optional routing policy. Returns the run ID and normalized configuration. |
| `POST /simulations/{id}/start` | Change `ready` to `running`. For orbital contact generation, the API starts a local playback task that advances the engine at a bounded fixed simulated-time step. Explicit-contact runs remain command-driven. |
| `POST /simulations/{id}/pause` | Change `running` to `paused`. |
| `POST /simulations/{id}/resume` | Change `paused` to `running`; orbital playback resumes in the API process. |
| `POST /simulations/{id}/step` | From `ready` or `paused`, process exactly one next engine event, preserving stable queue order. |
| `POST /simulations/{id}/advance` | From `running`, process up to `max_events` (1–10,000) through `target_time_us` (defaults to the current planned horizon). It does not use wall-clock duration. For orbital contact generation, the session extends the deterministic contact plan as needed to keep bundle-TTL lookahead; for explicit contacts, the configured horizon remains a hard stop. A response reports events processed and whether the target was reached. |
| `POST /simulations/{id}/reset` | Rebuild the run from its saved configuration and restore `ready` state. |

An inline configuration may specify circular-orbit elements for satellites and enable `orbital_contact_generation` with a contact sample interval, minimum ground-station elevation, and generated-link rate. In orbital mode, `horizon_us` is a minimum contact lookahead, not a stopping time. The initial plan reaches at least the latest configured bundle expiry; playback maintains a lookahead at least as long as the maximum configured bundle TTL, extending in deterministic batches. This lets contact-aware routing compare generated routes through their pre-expiry opportunities before selecting a hop. `bundle_generation_interval_us`, when set, repeats each configured bundle template at that simulated-time interval with deterministic IDs; `null` means only the configured bundles are generated. The returned horizon and contact count report current planned coverage; normalized configuration retains orbital, traffic, and contact-generation inputs so reset and export can reproduce them. Invalid lifecycle commands return 409. Invalid configuration or time bounds return 422. Unknown runs/resources return 404.

## Queries

| Method and path | Response |
|---|---|
| `GET /scenarios`, `GET /scenarios/{scenario_id}` | Registered preset summaries (purpose, node counts, contact mode, bundle counts) and validated normalized configurations. Presets: direct contact baseline, store-and-forward relay, intermittent multi-hop, relay buffer pressure, and moving LEO constellation. |
| `GET /simulations/{id}` | Lifecycle state, simulated time, horizon, seed, routing policy, and node/contact/bundle counts. |
| `GET /simulations/{id}/snapshot` | Full read-only current view with nodes, contacts, bundles, active transmissions, and ordered event history. |
| `GET /simulations/{id}/nodes`, `/nodes/{node_id}` | Node kind, configured buffer, current occupancy, engine-derived ECEF position/velocity, and orbital elements when applicable. |
| `GET /simulations/{id}/contacts` | Directed endpoints, interval, rate, propagation delay, and current status (`planned`, `active`, `interrupted`, or `completed`). |
| `GET /simulations/{id}/bundles`, `/bundles/{bundle_id}` | Bundle metadata, current holder/status, expiry, and successful forwarding records. |
| `GET /simulations/{id}/events?after_sequence=N&limit=100` | Ordered immutable events after the cursor. Limit is 1–1,000. |
| `GET /simulations/{id}/metrics` | Current-cutoff metrics and per-node/per-contact breakdowns; pending bundles remain undelivered, not expired. |
| `GET /simulations/{id}/export?format=json\|scenario_csv\|events_csv\|metrics_csv` | Downloadable current run manifest, configuration, event history, and/or metrics. |

All query responses are projections from immutable engine snapshots. They do not expose event queues or mutable engine objects. Bundle paths contain actual successful forwarding events only, with endpoint positions captured at the transmission/serialization times; the API does not invent a predicted delivery time. Contact status is derived from current simulated time and interruption history.

## Frontend update model

Poll run status and the compact snapshot while a run is active. Fetch event pages by sequence cursor and metrics when needed. For orbital runs, the API process advances simulated time by one simulated second about every 120 ms while the session is running; the dashboard only polls and renders snapshots. Closing the dashboard does not stop the run, but pausing or stopping/restarting the API does. The pacing task lives outside the engine; event timestamps and outcomes remain deterministic for a given configuration and requested advancement sequence. Explicit-contact runs still advance through bounded `/advance` commands. Consider WebSockets only if polling proves inadequate.

The Scenarios view reads summaries from `GET /scenarios` and loads one selected configuration from `GET /scenarios/{scenario_id}`. “Use this preset” copies that API-returned configuration into the dashboard’s next-run setup; it does not start a run or mutate an existing engine session. User-editable custom configurations remain a Simulation setup feature, separate from the read-only preset catalog.

## Current limitations

Only the in-memory run manager is provided; there is no authentication, persistence, durable job queue, dynamic topology editing after creation, or multi-process coordination. Orbital propagation is a circular two-body approximation with spherical Earth and sampled geometry windows, not a high-fidelity ephemeris or RF link budget.

The development API permits browser requests from `http://localhost:3000` and `http://127.0.0.1:3000` only. Expand this allowlist only when the local frontend origin changes.
