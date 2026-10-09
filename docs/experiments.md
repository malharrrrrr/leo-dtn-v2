# Experiments and metrics

## Research question

How do contact availability, buffer capacity, and routing strategy affect bundle delivery performance in a simulated LEO satellite network?

## Metric definitions

For a run horizon `H`, let `G` be the set of bundles whose generation event was attempted by `H`; retain an explicit record if source admission fails. Let `D` be bundles delivered by `H`. Confirmed project decision: include every attempted generation in the delivery-ratio denominator, including bundles rejected at the source because its buffer is full. At a fixed horizon, a bundle not yet delivered counts as undelivered for that horizon, but its queued, transmitting, or propagating state is reported separately and it is not reclassified as expired.

- **Delivery ratio:** `|D| / |G|`; define as not applicable when `|G| = 0`. A generation rejected at source is in `G` and cannot be delivered. This is the recommended denominator to avoid hiding source buffer failures.
- **Delivery latency:** per delivered bundle, `delivery_time - creation_time`; report mean, median, and count over delivered bundles only. Never assign synthetic latency to undelivered bundles.
- **Hop count:** successful receiver admissions for a delivered bundle; report delivered-bundle mean/median and count. An attempt or interrupted serialization is not a hop.
- **Expiration ratio:** terminal expirations by `H` divided by `|G|`; also report counts by cause/location if captured. This can be below one because bundles may remain pending at the horizon.
- **Buffer occupancy:** bytes in node buffers over simulation time; report per-node peak and the time-weighted mean (`integral occupied_bytes dt / measured duration`), plus normalized utilization against configured capacity. Declare handling for zero-duration runs.
- **Contact utilization:** successfully serialized payload bits divided by the sum of scheduled rate-bit capacity over the measured horizon for eligible directed contacts. Count only completed bundle serialization; interrupted partial bits are discarded in the initial model. Report per-contact and aggregate values. State whether contacts wholly/partly outside the horizon are clipped; recommend clipping scheduled capacity to `[0,H]`.

At horizon, distinguish delivered, expired, source-admission-rejected, queued, transmitting, and propagating bundles. A bundle not delivered by `H` is an outcome failure for delivery ratio at that cutoff, but it is **right-censored**, not automatically expired. Report its current status separately. Incomplete runs must be labeled as incomplete and must not be compared as if they shared a terminal horizon.

## Reproducibility record

Each run/export records schema version, scenario ID and normalized scenario/config, engine version/revision, routing policy and version, random seed, bundle-generation settings, simulation horizon, time/size/rate units, run completion status, metric definitions/version, and result/event history. Randomized placement and traffic use explicit independent seeded streams or a documented single stream; stable generation order is required. Export canonical JSON and CSV tables for events, bundles, metrics, and contacts. Never rely on an implicit default seed.

## Baseline comparisons and initial experiment plan

First validate mechanics with deterministic hand-checkable scenarios. Then compare the static minimum-hop baseline and contact-aware earliest-arrival policy on identical contact plans and bundle workloads. Vary one factor at a time initially: contact frequency/window length, buffer capacity, and offered bundle load/size. Keep other configuration fixed; record the seed. For randomized scenarios, use multiple declared seeds and report dispersion, not only the best run. Include no feasible route, bottleneck relay buffer, and intermittent relay contacts as diagnostic cases.

Do not claim statistical significance or operational satellite performance from a small illustrative run. Document the simplified contact plan, absent orbital dynamics, no fragmentation, and lack of custody acknowledgements as limitations.
