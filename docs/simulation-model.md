# Simulation model and initial semantics

These are recommended initial defaults to make the model coherent and testable. They are modelling choices, not claims about every DTN implementation or real satellite link.

## Clock and event queue

Use integer simulation ticks in microseconds from run start; no engine code reads wall-clock time. Input durations convert once to integer microseconds and must be finite/nonnegative; reject values that cannot be represented exactly under the chosen input precision rather than allowing float drift. Payloads use integer bytes; rates use integer bits/second; propagation delay uses integer microseconds.

The priority queue orders by `(timestamp, event_priority, insertion_sequence)`. Sequence is monotonically increasing and is the final stable tie-break. Proposed same-time priority: bundle expiration first; contact end/interruption second; contact start third; transmission serialization completion fourth; propagation arrival/receiver admission fifth; bundle generation sixth; routing/dispatch last. This ensures expiry at the delivery timestamp wins, and a contact beginning at a time is available to dispatch at that time. A completion cannot validly coincide with contact end because admission requires serialization to finish strictly before end. Priorities are part of the specification and tests.

Events scheduled at the current timestamp are accepted and processed by the same queue ordering, including a newly inserted event whose priority precedes another pending event at that timestamp. Events scheduled in the past are rejected. Zero-duration state transitions may be scheduled at current time, but a non-empty payload has positive serialization duration under the integer/positive-rate rules. Guard against unbounded same-time event loops (e.g. detect repeated zero-time transitions or impose a fail-fast event-count limit per timestamp). A finite explicit-contact run stops at its configured horizon. An orbital dashboard run treats its configured horizon as the initial contact-plan lookahead and extends the plan deterministically as simulated time approaches its end; the engine advances only when a caller requests it, never from wall-clock time.

Every contact-start event schedules a routing reevaluation at the same timestamp after contact starts have been processed. This is required for bundles already waiting in a buffer to use newly available contacts, including contacts appended by rolling plan extension.

Deterministic replay requires normalized config, explicit random seed, stable identifiers/iteration order, this ordering rule, and no dependence on hash iteration, wall clock, thread scheduling, or unseeded randomness.

## Nodes

Minimal `Satellite`: stable ID, finite buffer capacity in bytes, and either static scene coordinates or circular-orbit elements. Minimal `GroundStation`: stable ID, finite buffer capacity, and a fixed Earth-fixed coordinate. Shared buffer behavior uses one internal node representation with explicit node kind.

The initial moving-node model is a two-body **circular Kepler orbit**. Each satellite supplies altitude above a spherical Earth, inclination, right ascension of the ascending node (RAAN), and phase at simulation epoch. The engine uses Earth gravitational parameter `398600.4418 km^3/s^2` to compute mean motion, propagates position in ECI, then rotates by a constant Earth angular rate `7.2921150e-5 rad/s` into ECEF. It returns ECEF position and velocity at the current integer simulation tick. Ground stations are fixed in ECEF; latitude/longitude setup converts to a radius-6371-km point. The Earth mesh stays fixed in the frontend scene; satellite ECEF coordinates move as simulation time advances.

This model omits eccentricity, perturbations, precession, attitude, antenna patterns, terrain, weather, and Earth ellipsoid effects. Supplied static coordinates remain supported for hand-authored contact-plan tests and must not be presented as moving satellites. Seeded constellation placement is normalized to explicit orbital elements before the run. Topology cannot be edited during an active run.

## Contacts and topology

A contact has stable ID, directed `from_node` and `to_node`, start and end ticks, positive data rate in bits/second, and optional nonnegative propagation delay (default zero). Its availability interval is half-open `[start, end)`. Explicit contact plans remain supported. When orbital contact generation is enabled, the session generates a schedule through its current lookahead by sampling geometry at a declared interval (default 10 s) and bisecting detected visibility boundaries to microsecond resolution. As simulated time nears the lookahead, it regenerates the plan to a later horizon and merges newly discovered windows into the engine. Sampling can miss a visibility window shorter than its interval, which is a recorded model limitation. The displayed horizon in orbital mode is planned-contact coverage, not a simulation stop time.

Satellite-to-satellite contacts require the straight segment between current positions to clear the spherical Earth. A ground-station link additionally requires elevation at or above its configured minimum (default 10 degrees). For each visibility window, the planner emits two directed contacts, each with its own transmission resource; it does not imply full-duplex shared hardware. The configured link rate is applied to generated windows. Each generated window is fixed once planned, while later windows are added as lookahead extends; returned satellite states continue moving. Changing the interval, minimum elevation, link rate, orbit elements, or observation cutoff can change the plan and must be included in a reproducibility manifest. This is geometry-based contact generation, not an RF link budget or operational access prediction.

Reject missing endpoints, self-links, non-finite/invalid times, `start >= end`, nonpositive rates, negative delay, duplicate IDs, and overlapping contacts that contend for the same directed endpoint pair. The initial model has one transmission resource per directed contact and no parallel channels. Represent a bidirectional opportunity as two directed contacts, each with its own contention queue/resource. Overlap in opposite directions is allowed. This prevents ambiguous capacity accounting while keeping direction explicit.

## Transmission, contention, and interruption

Serialization duration is `ceil(payload_bytes * 8 * 1_000_000 / rate_bits_per_second)` microseconds, using integer arithmetic. A non-empty bundle needs at least one tick. Propagation delay is separate: after serialization completes, the receiver accepts the bundle at completion time plus propagation delay, subject to expiry and buffer checks then. The contact must remain active for the entire serialization interval: if start is `s`, duration `d`, and contact end `e`, require `s + d < e`. No new transmission begins at `e`.

At most one bundle serializes on a given directed contact at a time. Queued bundles contend in deterministic FIFO order by enqueue time then bundle ID; the routing policy may select a candidate but cannot bypass the shared contact resource. Contact capacity is derived from rate and duration, not a separate independent byte pool. Admission uses the whole bundle size; no fragmentation.

Initial policy: **restart from the beginning** after interruption. If a contact ends before serialization completion, the active attempt is interrupted, partial bits are discarded, and reserved resource is released. The sender retains the complete bundle and queues/retries it on a later feasible contact. The stale completion event is invalidated by an attempt token and has no effect. Already serialized data is not counted as delivered payload. No partial-fragment forwarding/resumption is modeled.

For deterministic failure tests, a scenario may include an exogenous contact interruption at an integer simulation timestamp strictly inside a scheduled contact window. This closes that contact at the interruption time, records and discards the partial transmitted bits, invalidates the pending completion, releases the contact resource, and leaves the complete bundle at the sender for a later contact. The failure is part of the normalized scenario input; it is not wall-clock or random behavior.

## Bundle lifecycle and finite storage

A bundle has unique ID, source, destination, positive payload bytes, creation tick, absolute expiry tick (`creation + TTL`), current holder while stored, status, ordered forwarding history, and visited-node set (or equivalent). Require source/destination to exist and TTL positive. Record every generation attempt; if source buffer cannot admit the bundle, mark it `rejected_at_source` without placing it in a buffer. Statuses distinguish `queued`, `transmitting`, `in_transit` (serialized, propagating), `delivered`, `expired`, and `rejected_at_source`; a failed/blocked attempt remains queued. Delivery, expiry, and source rejection are terminal.

Buffer capacity is bytes, with occupancy equal to sizes of bundles currently held in that node's queue or active outgoing serialization. Reject source creation or receiver admission if `occupancy + bundle_size > capacity`; do not evict another bundle. A receiver that cannot admit on arrival causes transfer failure and sender retains its bundle for a later attempt. Queues are FIFO by enqueue time then bundle ID; routing feasibility does not make storage infinite.

At a hop, sender retains its bundle through serialization and propagation. A successful transfer occurs only when the receiver admits the whole bundle after propagation and before expiry; then sender releases it and receiver becomes holder. If receiver is destination, the same acceptance event marks it delivered. Thus no period exists where neither endpoint owns the bundle. This is an atomic whole-bundle hop abstraction; it is not a BP custody acknowledgement.

On successful admission, append a forwarding record with from/to, contact ID, transmission start, serialization completion, and receiver acceptance ticks. Hop count is the count of successful receiver admissions. A node already in the bundle's visited set is not a valid next hop, preventing loops and duplicate return forwarding. A second arrival of an ID already held or terminal is rejected/ignored and recorded as a duplicate event; normal single-copy ownership should make this exceptional.

## Expiration

Expiry is an absolute tick computed at creation. A bundle is expired when `now >= expiry`; expiration priority precedes arrival/delivery at the same tick. Remove expired bundles from waiting buffers and cancel/invalidate active attempts/propagations; record one terminal expiration event. Any stale completion/arrival event checks bundle status, attempt token, and expiry before acting, so an expired bundle cannot be delivered later. Expiration during transmission releases the sender's reservation and discards the attempt; expiration during propagation prevents receiver admission.

## Optional recurring traffic

An optional `bundle_generation_interval_us` repeats a configured bundle template's source, destination, size, and TTL at fixed intervals of simulated time. The configured bundle is the first attempt; following IDs use deterministic suffixes (`-AUTO-000002`, and so on). Each copy has its own expiry, buffer admission, route, and metric outcome. This interval is simulation time, not a wall-clock timer. Recurring generation is intended for continuous interactive runs; experiment comparisons should use an explicit observation cutoff and include the interval in the manifest. A recurring stream keeps the engine event queue nonempty by design, so do not call unbounded `run_to_completion` for such a run.

## Routing boundary and initial policies

Routing receives an immutable decision view: current node/time, destination, bundle visited set/size/expiry, contacts (including future contacts only when declared), queue/resource state, and reachable neighbor buffer information. It proposes a next contact/neighbor; the engine validates and schedules the actual transmission. No route means retain until a later relevant state change or expire.

- **Feasible direct/shortest-hop baseline:** use currently active direct destination contact if available; otherwise choose the first hop on a minimum-hop path in the static union graph of known contacts. It ignores time ordering and is only a weak comparator; infeasible next hops wait/fail and can be misleading for intermittent networks. Do not call it time-dependent shortest path.
- **Contact-aware earliest-arrival policy:** on each forwarding decision, inspect future contact windows and choose a first hop on a feasible time-respecting route that minimizes predicted destination arrival under serialization plus propagation. This is a time-dependent earliest-arrival planner over a precomputed contact plan, not a named published algorithm. It knows future contacts but initially ignores other bundles' future contention, receiver admission failures, and uncertain contacts; engine execution remains authoritative. Re-evaluate after relevant events. If implementing only a local earliest-next-contact heuristic, label it that way and do not claim global earliest-arrival planning.

The routing interface must not mutate engine state. More complete queue-aware planning and published DTN algorithms are future work; see `routing.md`.

## First vertical slice: scenario and expected events

Nodes: `GS-A` (source ground station), `SAT-R` (relay satellite), `GS-B` (destination ground station); each buffer at least 1,000 bytes. Contacts: directed `GS-A -> SAT-R`, `[0, 10)` seconds at 8,000 bit/s, zero propagation; directed `SAT-R -> GS-B`, `[20, 30)` seconds at 8,000 bit/s, zero propagation. Bundle `B1`: 1,000 bytes, created at `t=2 s`, TTL 100 s (expires at 102 s), destination `GS-B`. The serialization duration is exactly 1 second.

Expected relevant event sequence:

1. `t=2`: create/admit B1 at `GS-A`; it is queued. A direct destination contact is unavailable.
2. `t=2`: start serialization on `GS-A -> SAT-R`.
3. `t=3`: serialization completes; receiver admits B1 at `SAT-R`, sender releases it; successful hop 1.
4. `t=3` through `t=20`: B1 remains queued in the relay buffer; no route/contact can deliver it sooner.
5. `t=20`: start serialization on `SAT-R -> GS-B`.
6. `t=21`: serialization completes; `GS-B` admits B1 and marks it delivered; successful hop 2.

Acceptance: no forwarding across unavailable time; relay retention is observable; delivery occurs only after both admissions; durations and timestamps match; identical config/seed yields identical event history. Unit tests run directly with Python and pytest, without FastAPI/frontend.

## Confirmed experiment interpretation

Count every attempted generation in the delivery-ratio denominator, including source-buffer rejection. At the run cutoff, count all bundles not delivered as undelivered for that horizon while reporting their actual state separately; do not label them expired unless their TTL has elapsed. See `experiments.md` for metric definitions.
