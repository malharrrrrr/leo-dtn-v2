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
| `POST /simulations/{id}/playback-speed` | Set local playback pacing to `0.25`, `0.5`, `1`, `2`, or `4` times the default display speed. This changes wall-clock pacing only; event time and routing semantics remain deterministic. |
| `POST /simulations/{id}/advance` | From `running`, process up to `max_events` (1–10,000) through `target_time_us` (defaults to the current planned horizon). It does not use wall-clock duration. For orbital contact generation, the session extends the deterministic contact plan as needed to keep bundle-TTL lookahead; for explicit contacts, the configured horizon remains a hard stop. A response reports events processed and whether the target was reached. |
| `POST /simulations/{id}/reset` | Rebuild the run from its saved configuration and restore `ready` state. |

An inline configuration may specify circular-orbit elements for satellites and enable `orbital_contact_generation` with a contact sample interval, minimum ground-station elevation, and generated-link rate. In orbital mode, `horizon_us` is a minimum contact lookahead, not a stopping time. The initial plan reaches at least the latest configured bundle expiry; playback maintains a lookahead at least as long as the maximum configured bundle TTL, extending in deterministic batches. This lets contact-aware routing compare generated routes through their pre-expiry opportunities before selecting a hop. `bundle_generation_interval_us`, when set, repeats each configured bundle template at that simulated-time interval with deterministic IDs; `null` means only the configured bundles are generated. The returned horizon and contact count report current planned coverage; normalized configuration retains orbital, traffic, and contact-generation inputs so reset and export can reproduce them. Invalid lifecycle commands return 409. Invalid configuration or time bounds return 422. Unknown runs/resources return 404.

## Queries

| Method and path | Response |
|---|---|
| `GET /scenarios`, `GET /scenarios/{scenario_id}` | Selectable preset summaries (purpose, node counts, contact mode, bundle counts) and validated normalized configurations. The five selectable presets share the default moving Mumbai–New York LEO setup and vary satellite count, buffer capacity, or traffic. The hand-checkable `relay-vertical-slice` remains directly addressable for engine verification but is not presented as a moving-LEO preset. |
| `GET /simulations/{id}` | Lifecycle state, simulated time, horizon, seed, routing policy, and node/contact/bundle counts. |
| `GET /simulations/{id}/snapshot` | Full read-only current view with nodes, contacts, bundles, active transmissions, and ordered event history. |
| `GET /simulations/{id}/nodes`, `/nodes/{node_id}` | Node kind, configured buffer, current occupancy, engine-derived ECEF position/velocity, and orbital elements when applicable. |
| `GET /simulations/{id}/contacts` | Directed endpoints, interval, rate, propagation delay, and current status (`planned`, `active`, `interrupted`, or `completed`). |
| `GET /simulations/{id}/bundles`, `/bundles/{bundle_id}` | Bundle metadata, current holder/status, expiry, and successful forwarding records. |
| `GET /simulations/{id}/events?after_sequence=N&limit=100` | Ordered immutable events after the cursor. Limit is 1–1,000. |
| `GET /simulations/{id}/metrics` | Current-cutoff metrics and per-node/per-contact breakdowns; pending bundles remain undelivered, not expired. |
| `POST /experiments/compare` | Run both routing policies for each requested selectable preset using the same seed and cutoff; returns paired scenario metadata and backend-calculated metrics. |
| `GET /simulations/{id}/export?format=json\|scenario_csv\|events_csv\|metrics_csv` | Downloadable current run manifest, configuration, event history, and/or metrics. |

`POST /experiments/compare` accepts `scenario_ids` (1–5 unique IDs), `random_seed` (integer, default `42`), and `horizon_us` (60,000,000–3,600,000,000, default `600,000,000`). It executes fresh isolated engine runs for `contact_aware_earliest_arrival` and `static_minimum_hop` on the same scenario inputs, then returns the `MetricsResponse` for each policy under each scenario. Orbital contact plans cover the configured bundle TTL even when the observation cutoff is shorter; the returned metrics are measured at that cutoff. The endpoint does not create or modify a live simulation session. Unknown or non-selectable scenario IDs return 404.

All query responses are projections from immutable engine snapshots. They do not expose event queues or mutable engine objects. Each bundle retains its actual successful forwarding records for the full in-memory run, and the snapshot includes every bundle rather than only the currently selected one. The dashboard can therefore build a run-wide transfer ledger while preserving each bundle's full path. Forwarding records include endpoint positions captured at the transmission/serialization times; the API does not invent a predicted delivery time. Contact status is derived from current simulated time and interruption history.

## Frontend update model

Poll run status and the compact snapshot while a run is active. Fetch event pages by sequence cursor and metrics when needed. For orbital runs, the API process advances simulated time by one simulated second about every 120 ms at `1×`; the dashboard can select `0.25×`, `0.5×`, `1×`, `2×`, or `4×`. The dashboard polls and renders snapshots. Closing the dashboard does not stop the run, but pausing or stopping/restarting the API does. The pacing task lives outside the engine; event timestamps and outcomes remain deterministic for a given configuration and requested advancement sequence. Explicit-contact runs advance through bounded `/advance` commands using the selected simulated-time increment. Consider WebSockets only if polling proves inadequate.

The Scenarios view reads summaries from `GET /scenarios` and loads one selected configuration from `GET /scenarios/{scenario_id}`. “Use this preset” copies that API-returned configuration into the dashboard’s next-run setup; it does not start a run or mutate an existing engine session. User-editable custom configurations remain a Simulation setup feature, separate from the read-only preset catalog.

## Current limitations

Only the in-memory run manager is provided; there is no authentication, persistence, durable job queue, dynamic topology editing after creation, or multi-process coordination. Orbital propagation is a circular two-body approximation with spherical Earth and sampled geometry windows, not a high-fidelity ephemeris or RF link budget.

The development API permits browser requests from `http://localhost:3000` and `http://127.0.0.1:3000` only. Expand this allowlist only when the local frontend origin changes.
