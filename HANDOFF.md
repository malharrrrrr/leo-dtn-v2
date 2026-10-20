# LEO-DTN agent handoff

**Last reviewed:** 2026-10-21

**Purpose:** Give a new agent enough context to navigate the repository, run it safely, and continue work without losing local changes or confusing modeled behavior with real system behavior.

## Start here

1. Read this file, then `AGENTS.md` for non-negotiable working rules.
2. Read `PROJECT.md`, `ROADMAP.md`, `docs/architecture.md`, and `docs/simulation-model.md` before changing simulation or architecture behavior. Read `docs/routing.md`, `docs/api-contract.md`, or `docs/experiments.md` for work in those areas.
3. Run `git status --short` and inspect relevant `git diff` before editing. Preserve any user changes already present; do not reset, clean, overwrite, or assume all modifications are yours.
4. Make one focused change, update the relevant documentation and this handoff when project status materially changes, then run the checks relevant to that change.

## Project in one minute

LEO-DTN is a local academic simulator for delay-tolerant, store-carry-forward bundles over time-varying satellite contacts. A deterministic discrete-event Python engine owns simulated state. FastAPI exposes commands and read-only snapshots. A Next.js/React/TypeScript dashboard configures runs and displays engine-returned nodes, contacts, bundles, and metrics.

This is not a real satellite communications system. Satellite motion is currently a simplified circular two-body model; contact windows are geometry-derived and generated with a rolling lookahead for orbital runs. Do not claim full Bundle Protocol compliance, operational performance, high-fidelity ephemerides, or RF link-budget realism.

## Repository map

| Path | What to look at |
|---|---|
| `AGENTS.md` | Required boundaries, Python venv, verification, and change practices |
| `PROJECT.md` | Scope, objectives, constraints, non-goals |
| `ROADMAP.md` | Milestone status and acceptance criteria; keep this current |
| `README.md` | User-facing project summary and local startup instructions |
| `docs/architecture.md` | Engine/API/UI responsibilities and data flow |
| `docs/simulation-model.md` | Clock, event priorities, contacts, forwarding, storage, TTL, orbit model, first scenario |
| `docs/routing.md` | Routing policies and limitations |
| `docs/api-contract.md` | REST commands, queries, and DTOs |
| `docs/experiments.md` | Metrics, run manifests, and reproducibility |
| `backend/leo_dtn/model.py` | Immutable domain values and snapshots |
| `backend/leo_dtn/engine.py` | Event queue and all bundle/contact state transitions |
| `backend/leo_dtn/orbit.py` | Circular orbit propagation, line-of-sight, contact-plan generation |
| `backend/leo_dtn/routing.py` | Earliest-arrival and minimum-hop routing policies |
| `backend/leo_dtn/service.py` | In-memory simulation sessions, validation mapping, run controls |
| `backend/leo_dtn/api_models.py` | Pydantic HTTP request/response models |
| `backend/leo_dtn/api.py` | FastAPI routes and serialization boundary |
| `backend/leo_dtn/metrics.py` | Pure run metric calculations |
| `backend/leo_dtn/experiments.py` | Reproducible runs, manifests, JSON/CSV exports |
| `backend/leo_dtn/scenarios.py` | Hand-checkable relay vertical slice |
| `backend/tests/` | Engine, metrics, orbit, experiment, and API tests |
| `frontend/src/app/page.tsx` | Next.js entry route (`/`) |
| `frontend/src/components/dashboard.tsx` | Configuration, controls, polling, panels, selected run state |
| `frontend/src/components/scenario-library.tsx` | API-backed scenario preset catalog and detail view |
| `frontend/src/components/network-scene.tsx` | Three.js globe, nodes, contacts, orbit trails, selected bundle |
| `frontend/src/components/network-topology.tsx` | SVG topology view |
| `frontend/src/lib/api.ts` | Frontend REST calls |
| `frontend/src/lib/contracts.ts` | TypeScript API data contracts |
| `frontend/src/app/globals.css` | Dashboard styling |

## Important behavior and boundaries

- The engine is callable directly from Python; it has no HTTP, frontend, or wall-clock dependency. Do not move routing or simulation decisions into React or FastAPI.
- Simulation timestamps and rates use integer microseconds and bits per second. Event order is timestamp, documented priority, then stable insertion sequence.
- Contacts are directed half-open windows `[start, end)`. A complete bundle serialization must fit before contact close. On interruption, the full bundle remains at the sender and transmission restarts later; there is no fragmentation/resumption.
- The sender holds a bundle until the receiver accepts it after serialization and propagation. A queued bundle at a relay is expected to stay there while waiting for a valid future contact; it must not be animated across a gap.
- The frontend’s 3D globe is based on engine-returned ECEF state. Earth stays fixed in scene coordinates; manual camera rotation is allowed. Packet-follow moves the view camera to the selected bundle. Active-transmission marker movement uses engine time; queued bundles remain at their holder.
- Keep future contact windows, current links, and historical forwarding clearly distinct in the UI.
- The current frontend has the dashboard at `/`. There is no `/analysis` route yet; a request to `/analysis` returns 404. The Experiments navigation item is not a completed analysis page.
- Orbital sessions now advance in an API-owned task while the API process is alive, even when the browser is closed. The task requests deterministic one-second simulation advances about every 120 ms; pausing stops advancement. The engine itself remains free of wall-clock reads. Explicit-contact runs are still advanced through API commands.
- Orbital contact generation plans initially through the latest configured bundle expiry, even when the requested minimum horizon is shorter. During playback it maintains at least the maximum configured bundle TTL ahead of simulation time, extending deterministically in one-hour batches (with a 120-second minimum for short/no-TTL scenarios). This lets contact-aware earliest-arrival routing compare contacts through a bundle's expiry before missing earlier first hops. The regression uses the default Mumbai/New York constellation and verifies BND-001 starts via SAT-01 at t=2s with a 600-second requested minimum. Geometry sampling can still miss short windows; route estimates also ignore future contention and admission failures.
- Configured bundles repeat at `bundle_generation_interval_us`; the dashboard default is one bundle every 60 simulated seconds. Each repeat has a deterministic ID and ordinary buffer, route, TTL, and metric behavior; the rolling plan stays ahead by the template TTL.
- Contact starts now wake queued bundles for a routing reevaluation. This matters for contacts added by rolling plan extension; without that wake-up a bundle could remain buffered after its new contact became active. The dashboard's default bundle TTL is six hours so it can survive longer store-carry-forward waits between distant ground stations.
- Successful forwarding records remain on each bundle in every engine snapshot. The dashboard groups transfer hops under individual bundles, keeps earlier bundles visible as new traffic moves, and lets each bundle/hop select that bundle for full path inspection. The bundle list starts with the latest 12 and reveals older bundles in pages of 12.
- The 3D globe now renders a stable, bundle-ID-specific marker for every bundle in the run. Markers follow engine-reported transmission progress or stay at the bundle's holder; delivered and expired bundles remain inspectable at their terminal location. Bundles sharing a node are fanned out slightly for visibility (a visual offset only). Clicking a marker selects that bundle and updates the details/follow view. Verify this interactively with several queued and completed bundles; the canvas marker hit-testing is local UI behavior only and does not affect engine state.
- Playback controls include state-aware play/pause, one-event stepping, reset, and 0.25×/0.5×/1×/2×/4× pacing. The API-owned orbital playback uses the selected pace; explicit-contact runs advance by a speed-scaled simulated-time increment. Playback speed is adapter pacing, not engine time logic, and reset restores 1×.
- Dashboard defaults now place the ground stations in Mumbai and New York so a long relay path is more visible. The source default is Mumbai and destination is New York.
- The Scenarios tab exposes five variants of the default moving Mumbai–New York LEO setup: baseline, four-satellite sparse constellation, limited satellite buffers, higher bundle load, and expanded 16-satellite constellation. The orbital presets share the default endpoint, orbit model, and recurring traffic unless that factor is the experiment being varied. The fixed-contact relay vertical slice remains a backend verification fixture and is not shown as an orbital preset. “Use this preset” loads its API-returned configuration for the next run without starting or changing the active engine.
- The dashboard uses locally bundled Next.js font assets for Manrope interface text and IBM Plex Mono metrics/IDs, alongside the visual refinement to spacing and panel hierarchy. No simulation behavior or API contract changed.

## Run and verify locally

Use Windows PowerShell from the repository root unless the user specifies otherwise. Backend commands must use the existing project venv; never use system Python or install dependencies without a task that calls for it.

```powershell
# API terminal, from repository root
backend/.venv/Scripts/python.exe -m uvicorn leo_dtn.api:app --app-dir backend --reload

# Frontend terminal, from repository root
cd frontend
npm run dev
```

Open `http://localhost:3000/`. The dashboard calls `http://127.0.0.1:8000` by default. `frontend/next.config.ts` allows the dev HMR origin `127.0.0.1`; restart Next.js after changing this config.

```powershell
# From repository root
backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q backend/tests

# From frontend/
npm run typecheck
npm run lint
npm run build
```

On Unix, use `backend/.venv/bin/python`. Do not make engine tests depend on running FastAPI; API tests may start a local Uvicorn subprocess to test the HTTP boundary.

## Current checkout and known state

- Always inspect `git status --short` and relevant diffs before edits; preserve unrelated user changes. This handoff describes the committed project state, not a promise that a future checkout is clean.
- The implementation includes a deterministic event engine, finite bundle buffers and lifecycle, two routing policies, metrics/exports, FastAPI controls, circular orbital motion, and geometry-derived contacts.
- The dashboard has a configurable constellation, seeded satellite placement, a Three.js globe, topology view, playback controls, bundle/node/network panels, and engine-state polling. The default minimum contact-plan horizon is 600 seconds; orbital sessions extend actual planned coverage through bundle TTL.
- Recent frontend terminal fixes: trails are drawn only after at least two samples (avoids Three.js empty-geometry warnings); Next dev origin allows `127.0.0.1`. Restart the dev server to load that Next config.
- A logged `GET /analysis 404` is expected until an analysis route is deliberately implemented. It does not prevent the `/` dashboard from running.
- Latest verification: `backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q` passed (50 tests; local Uvicorn tests require local socket access). From `frontend/`, `npm run typecheck`, `npm run lint`, and `npm run build` passed. A sandboxed build hit Windows path canonicalization permissions; the same build passed with filesystem access.
- Latest grouped-history/playback verification: from `frontend/`, `npm run typecheck` and `npm run lint` passed; `backend/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'backend'); from leo_dtn.api import app"` imported the API models/routes successfully. The venv prints `Failed to find real location of C:\Python314\python.exe` before continuing, even though the import succeeds; do not fall back to system Python. No pytest suite was run in this prompt.
- Latest multi-bundle marker verification: from `frontend/`, `npm run typecheck` and `npm run lint` passed after adding per-bundle globe markers and click-to-select. No engine code or Python tests changed. This working change is intentionally uncommitted at the user's direction; `frontend/next-env.d.ts` also remains modified from Next.js dev-generated route type references.
- Latest visual refinement verification: from `frontend/`, `npm run typecheck`, `npm run lint`, and `npm run build` all passed on 2026-10-21. Next.js font optimization downloads Manrope and IBM Plex Mono during build; the font assets are then bundled with the app. The build regenerated `next-env.d.ts`; its prior dev-route references were restored and excluded from this change.
- Current working branch is `feat/scnearios`. Preserve the pre-existing local `frontend/next-env.d.ts` change (`.next/dev/types` imports); it is unrelated to scenario presets and must not be included in their commit.
- The working roadmap says circular-orbit/contact behavior is implemented but still needs long-run and interactive validation. Do not mark those milestones complete based only on compilation.

## Suggested next task

Launch the API and dashboard, open `/`, and verify multiple bundle markers remain distinguishable while queued at one node, move along active transfers, and can be clicked to inspect and follow the selected bundle. Confirm marker stacking is only a visual separation and bundle status/history still comes from engine snapshots. Also verify transfers stay grouped by bundle as new bundles move, playback controls work at each speed, and the Scenarios presets still load. Continue long-run orbital validation: contacts and recurring traffic continue as intended, relay queues resume on new contacts, and packet-follow keeps the selected bundle visible. Keep `/analysis` explicitly deferred unless experiment analysis is chosen as the next product task.

After substantial work, update this file’s current state, verification results, and suggested next task so another agent can resume without reconstructing the entire conversation.
