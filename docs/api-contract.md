# API contract

The REST layer is an adapter around the Python engine. Pydantic validates inputs and shapes outputs; it does not implement routing, contact selection, or bundle transitions. Runs live in memory for the lifetime of one API process. Restarting the process loses them.

## Commands

| Method and path | Purpose |
|---|---|
| `POST /simulations` | Create from one registered `scenario_id` or an inline `configuration`, plus required `random_seed`, `horizon_us`, and optional routing policy. Returns the run ID and normalized configuration. |
| `POST /simulations/{id}/start` | Change `ready` to `running`; does not advance simulated time. |
| `POST /simulations/{id}/pause` | Change `running` to `paused`. |
| `POST /simulations/{id}/resume` | Change `paused` to `running`. |
| `POST /simulations/{id}/step` | From `ready` or `paused`, process exactly one next engine event, preserving stable queue order. |
| `POST /simulations/{id}/advance` | From `running`, process up to `max_events` (1–10,000) through `target_time_us` (defaults to the configured horizon). It does not use wall-clock duration. A response reports events processed and whether the target was reached. |
| `POST /simulations/{id}/reset` | Rebuild the run from its saved configuration and restore `ready` state. |

Invalid lifecycle commands return 409. Invalid configuration or time bounds return 422. Unknown runs/resources return 404. A created run records its seed; random generation is not yet used by the fixed relay scenario.

## Queries

| Method and path | Response |
|---|---|
| `GET /scenarios`, `GET /scenarios/{scenario_id}` | Registered scenario summaries and validated configuration. Initially includes `relay-vertical-slice`. |
| `GET /simulations/{id}` | Lifecycle state, simulated time, horizon, seed, routing policy, and node/contact/bundle counts. |
| `GET /simulations/{id}/snapshot` | Full read-only current view with nodes, contacts, bundles, active transmissions, and ordered event history. |
| `GET /simulations/{id}/nodes`, `/nodes/{node_id}` | Node kind, configured buffer, current occupancy, and optional model position. |
| `GET /simulations/{id}/contacts` | Directed endpoints, interval, rate, propagation delay, and current status (`planned`, `active`, `interrupted`, or `completed`). |
| `GET /simulations/{id}/bundles`, `/bundles/{bundle_id}` | Bundle metadata, current holder/status, expiry, and successful forwarding records. |
| `GET /simulations/{id}/events?after_sequence=N&limit=100` | Ordered immutable events after the cursor. Limit is 1–1,000. |
| `GET /simulations/{id}/metrics` | Current-cutoff metrics and per-node/per-contact breakdowns; pending bundles remain undelivered, not expired. |
| `GET /simulations/{id}/export?format=json\|scenario_csv\|events_csv\|metrics_csv` | Downloadable current run manifest, configuration, event history, and/or metrics. |

All query responses are projections from immutable engine snapshots. They do not expose event queues or mutable engine objects. Bundle paths contain actual successful forwarding events only; the API does not invent a predicted delivery time. Contact status is derived from current simulated time and interruption history.

## Frontend update model

Poll run status and the compact snapshot while a run is active. Fetch event pages by sequence cursor and metrics when needed. `start` alone does not create a wall-clock worker: the client issues bounded `/advance` commands. This keeps simulation time deterministic and the engine transport-independent. Consider WebSockets only if polling proves inadequate.

## Current limitations

Only the in-memory run manager is provided; there is no authentication, persistence, durable job queue, dynamic topology editing after creation, or multi-process coordination. The current API does not expose velocity or upcoming orbital contacts because the engine does not calculate them.

The development API permits browser requests from `http://localhost:3000` and `http://127.0.0.1:3000` only. Expand this allowlist only when the local frontend origin changes.
