# Implementation roadmap

No deadlines are assigned. Each milestone has an independently checkable exit condition. Later work depends on earlier semantics and tests; advanced orbital fidelity is optional unless the academic evaluation requires it.

## 1. Specification and architecture (current)

**Deliverables:** `PROJECT.md`, `AGENTS.md`, architecture, model, experiments, routing/API contracts, and this roadmap.

**Acceptance:** documents agree on units, event ordering, transfer/expiry behavior, boundaries, first scenario, and metric definitions. No application code is required in this milestone.

## 2. Minimal deterministic engine

**Depends on:** milestone 1.

**Deliverables:** directly callable simulation clock/event queue, minimal nodes and fixed contact plan, one bundle, complete hop transmission, immutable snapshots/event records, and vertical-slice scenario.

**Acceptance:** pytest proves ordered events, unavailable links cannot carry data, relay retention, correct serialization/arrival timestamps, successful delivery only after valid hops, and identical replay. Tests run without FastAPI or frontend.

## 3. Bundle lifecycle, contacts, buffers, and routing

**Depends on:** milestone 2.

**Deliverables:** admission/overflow, TTL and expiry, interrupted transmission behavior, duplicate/loop rules, resource contention, baseline and contact-aware policy interfaces.

**Acceptance:** focused tests cover each boundary and simultaneous expiry/delivery. Failed or infeasible contacts cannot create a delivery; finite buffers are enforced; routing can be replaced without changing engine event semantics.

## 4. Metrics and reproducible experiments

**Depends on:** milestones 2–3.

**Deliverables:** metric aggregation, scenario/config schema, explicit random seed, run manifest, JSON/CSV exports, and experiment runner callable locally.

**Acceptance:** hand-calculated fixtures validate denominators and cutoff cases; repeated seeded runs produce identical manifests/results; comparisons vary one declared factor at a time or document factorial design.

## 5. FastAPI integration and controls

**Depends on:** stable engine API from milestones 2–4.

**Deliverables:** implemented in-memory run manager, scenario/run commands, status and state queries, bounded advance, validation errors, and JSON/CSV export endpoints. The engine remains importable and directly testable without the API.

**Acceptance:** API/engine integration tests verify command validation, state transitions, response snapshots, event cursors, exports, and that API code contains no forwarding/routing semantics. The API tests run against a local Uvicorn subprocess to exercise the real HTTP boundary.

## 6. Frontend dashboard and visualization

**Depends on:** API response contract and stable snapshots.

**Deliverables:** three-region dark technical dashboard; scenario/routing/config controls; preset/custom satellite counts; add/remove and explicit/seeded-random satellite placement; globe/map/topology view; playback/time controls; selected bundle/node/network panels; metrics and empty/loading/error states. In 3D, Earth remains stationary unless the user rotates the view; optional packet-follow adjusts the camera based on engine state.

**Acceptance:** frontend uses API state only for simulation behavior, handles changing satellite counts without fixed-slot assumptions, seeded placement reproduces the same realized configuration, and topology edits apply before run creation. Earth does not spin automatically; manual rotation works; packet-follow keeps a selected bundle in view and only interpolates over a real active transmission. Link/bundle history remains accurate, simulation lifecycle states are handled, and layout is usable at ordinary laptop widths. Type-check, lint, and focused component tests pass.

## 7. LEO-specific contact generation and scenario realism

**Depends on:** validated contact and node interfaces; justified by evaluation needs.

**Deliverables:** documented orbital/contact assumptions and a contact-plan generator, with deterministic inputs and independent validation fixtures. Add orbital position fields only when a selected model supports them.

**Acceptance:** generated contact plans obey declared geometry/visibility assumptions and are reproducible. Do not claim realistic fidelity beyond the validated model. Orbital propagation and 3D rendering library choices remain open until requirements are evaluated.

## 8. End-to-end validation and academic evaluation

**Depends on:** selected final feature scope from milestones 1–7.

**Deliverables:** end-to-end scenarios, reproducible experiment outputs, limitations, architecture/model documentation, and report-ready plots/tables.

**Acceptance:** documented experiments answer the research question with repeated runs or controlled deterministic scenarios, results can be regenerated from manifests, and claims match implemented behavior. No advanced feature is required unless it supports a stated evaluation objective.

## Deferred work

Fragmentation/resumption, BP custody and acknowledgements, multiple channels, dynamic orbital propagation, WebSockets, database persistence, authentication, distributed execution, and operational satellite fidelity are deferred. Revisit only with a concrete requirement and documented semantics.
