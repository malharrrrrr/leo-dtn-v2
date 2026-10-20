# Implementation roadmap

No deadlines are assigned. Each milestone has an independently checkable exit condition. Circular orbital motion and geometry-based contact loss are core project behavior; high-fidelity orbital and RF modelling remain out of scope.

## 1. Specification and architecture (complete)

**Deliverables:** `PROJECT.md`, `AGENTS.md`, architecture, model, experiments, routing/API contracts, and this roadmap.

**Acceptance:** documents agree on units, event ordering, transfer/expiry behavior, boundaries, first scenario, and metric definitions. No application code is required in this milestone.

## 2. Minimal deterministic engine (complete)

**Depends on:** milestone 1.

**Deliverables:** directly callable simulation clock/event queue, minimal nodes and fixed contact plan, one bundle, complete hop transmission, immutable snapshots/event records, and vertical-slice scenario.

**Acceptance:** pytest proves ordered events, unavailable links cannot carry data, relay retention, correct serialization/arrival timestamps, successful delivery only after valid hops, and identical replay. Tests run without FastAPI or frontend.

## 3. Bundle lifecycle, contacts, buffers, and routing (complete)

**Depends on:** milestone 2.

**Deliverables:** admission/overflow, TTL and expiry, interrupted transmission behavior, duplicate/loop rules, resource contention, baseline and contact-aware policy interfaces.

**Acceptance:** focused tests cover each boundary and simultaneous expiry/delivery. Failed or infeasible contacts cannot create a delivery; finite buffers are enforced; routing can be replaced without changing engine event semantics.

## 4. Metrics and reproducible experiments (engine support complete; dashboard analysis pending)

**Depends on:** milestones 2–3.

**Deliverables:** metric aggregation, scenario/config schema, explicit random seed, run manifest, JSON/CSV exports, and experiment runner callable locally.

**Acceptance:** hand-calculated fixtures validate denominators and cutoff cases; repeated seeded runs produce identical manifests/results; comparisons vary one declared factor at a time or document factorial design.

## 5. FastAPI integration and controls (initial integration complete)

**Depends on:** stable engine API from milestones 2–4.

**Deliverables:** implemented in-memory run manager, scenario/run commands, status and state queries, bounded advance, validation errors, and JSON/CSV export endpoints. The engine remains importable and directly testable without the API.

**Acceptance:** API/engine integration tests verify command validation, state transitions, response snapshots, event cursors, exports, and that API code contains no forwarding/routing semantics. The API tests run against a local Uvicorn subprocess to exercise the real HTTP boundary.

## 6. Frontend dashboard and visualization (first pass implemented; visual refinement completed, interaction validation pending)

**Depends on:** API response contract and stable snapshots.

**Deliverables:** implemented first dashboard slice with three-region dark layout; routing/config controls; add/remove and explicit/seeded-random satellite placement; 3D globe and topology views; playback/time controls; selected bundle/node/network panels; metrics and empty/loading/error states; an API-backed preset library using the same moving Mumbai–New York LEO model as the Simulation default, with controlled variants for satellite count, buffer capacity, and traffic. Presets are inspectable and load into next-run configuration without starting a run. The fixed-contact relay vertical slice remains an engine fixture, not a displayed orbital scenario. A geographic map is deferred because coordinates are scene-frame XYZ, not latitude/longitude. In 3D, Earth remains stationary unless the user rotates the view; packet-follow adjusts the camera target from engine state.

**Acceptance:** frontend uses engine snapshots for orbital state, contact activity, and bundle behavior; handles changing satellite counts without fixed-slot assumptions; seeded placement produces identical elements; topology edits apply before run creation; and preset catalog/detail views use API-returned configuration and metadata. Loading a preset changes next-run configuration without starting or mutating a run. Earth remains fixed; manual rotation works; satellites visibly move; geometry-derived links appear only while in line of sight and disappear when visibility ends; packet-follow keeps a selected bundle in view and marker movement follows actual active transmission state. The right panel retains successful transfer hops grouped by bundle across the in-memory run, and selecting a bundle/hop opens that bundle's forwarding path. Playback has state-aware play/pause, single-event stepping, reset, and an API-backed speed selector that changes display pacing without changing engine semantics. Link/bundle history remains accurate, simulation lifecycle states are handled, and layout is usable at ordinary laptop widths. Type-check, lint, production build, and interaction-level frontend tests pass.

## 7. Circular orbit, geometry-derived contacts, and continuous playback (core behavior implemented; validation in progress)

**Depends on:** validated contact and node interfaces.

**Deliverables:** implemented circular Kepler position propagation, fixed Earth-frame ground stations, engine-returned ECEF state/velocity, and reproducible line-of-sight contact generation with a rolling lookahead for continuous orbital playback. Orbital routing plans through configured bundle expiry and maintains TTL-sized coverage for recurring traffic. The dashboard can generate recurring bundle traffic at a configured simulation-time interval.

**Acceptance:** positions change deterministically with simulated time; generated contacts obey the declared spherical-Earth and minimum-elevation model, disappear at computed window end, the rolling plan continues beyond its minimum horizon and covers bundle TTL, and identical inputs replay identically. A regression proves the initial route uses an early viable contact even when delivery requires contacts beyond the requested minimum horizon. Recurring bundle IDs and generation times are deterministic. State clearly that this is simplified orbital propagation, not a high-fidelity operational model. Validate long-run cost and browser playback interactively before calling the milestone complete.

## 8. End-to-end validation and academic evaluation

**Depends on:** milestones 1–7.

**Deliverables:** end-to-end scenarios, reproducible experiment outputs, limitations, architecture/model documentation, and report-ready plots/tables.

**Acceptance:** documented experiments answer the research question with repeated runs or controlled deterministic scenarios, results can be regenerated from manifests, and claims match implemented behavior. No advanced feature is required unless it supports a stated evaluation objective.

## Deferred work

Fragmentation/resumption, BP custody and acknowledgements, multiple channels, orbital perturbations, high-fidelity ephemerides, RF link budgets, WebSockets, database persistence, authentication, distributed execution, and operational satellite fidelity are deferred. Revisit only with a concrete requirement and documented semantics.
