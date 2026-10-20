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

The initial local runner records the seed even when the supplied scenario is already fully specified and needs no random draws. Geometry-based runs must also record orbital elements, spherical Earth/constants version, contact sampling interval, minimum elevation, link rate, observation cutoff, and initial lookahead. Recurring traffic records its generation interval alongside the bundle template. JSON contains the manifest, normalized scenario, event history, and metrics. CSV exports provide normalized scenario rows, ordered events, and metric rows. A run status of `completed_to_horizon` means the requested observation cutoff was reached; it does not mean every bundle was delivered or expired.

## Baseline comparisons and initial experiment plan

First validate mechanics with deterministic hand-checkable scenarios. Then compare the static minimum-hop baseline and contact-aware earliest-arrival policy on identical contact plans and bundle workloads. Vary one factor at a time initially: contact frequency/window length, buffer capacity, and offered bundle load/size. Keep other configuration fixed; record the seed. For randomized scenarios, use multiple declared seeds and report dispersion, not only the best run. Include no feasible route, bottleneck relay buffer, and intermittent relay contacts as diagnostic cases.

Do not claim statistical significance or operational satellite performance from a small illustrative run. Document that orbital motion uses two-body circular Kepler propagation and a spherical Earth; geometry sampling can miss windows shorter than its interval; no RF link budget, fragmentation, or custody acknowledgements are modelled.

## Dashboard comparison

The Metrics & comparison view runs both routing policies through the backend for the selected API presets, seed, and observation cutoff. Each pair shares identical nodes, generated orbital contacts, bundle workload, seed, and cutoff; only the routing policy changes. The five initial settings are the default constellation, sparse constellation, limited satellite buffers, high traffic, and expanded constellation. The default dashboard selection runs all five presets at seed `42` and a 3,600-second cutoff. This is five controlled settings, not five independent randomized replications.

The view defaults to a 3,600-second observation cutoff so the initial comparison includes more orbital contact opportunities; users can choose cutoffs from 60 to 3,600 seconds. It ranks each pair lexicographically by delivery ratio (higher), median delivery latency among delivered bundles (lower), then mean hop count among delivered bundles (lower). A displayed leader therefore leads on the first metric that differs under that ordering; it does not imply universal superiority. Expiration ratio is a separate outcome and pending bundles remain right-censored at the cutoff. Contact utilization and time-weighted mean total buffer occupancy are contextual metrics with no universally better direction. The view reports both algorithms' bundle counts and explains that one small deterministic run does not establish statistical significance or equivalence.

The comparison endpoint accepts scenario IDs, seed, and cutoff as documented in `api-contract.md`. Formulas follow the metric definitions above; displayed latencies are converted from engine microseconds to seconds, while the API retains microseconds.
