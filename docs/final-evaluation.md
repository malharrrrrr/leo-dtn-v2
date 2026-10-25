# Final evaluation guide

## Study question

How do contact availability, buffer capacity, and routing strategy affect bundle delivery performance in this simplified LEO network model?

## Reproduce the dashboard comparison

1. Start the local API and dashboard using the commands in `README.md`.
2. Open **Metrics & comparison**. The baseline preset is selected for the starter run.
3. Keep the default observation cutoff at 3,600 seconds for the reference comparison. Set a starting seed and choose 3 or 5 consecutive seeds for a descriptive repeat.
4. Run the baseline pair, then add one controlled preset at a time: sparse constellation, limited buffers, high traffic, or expanded constellation.
5. Download the run-level CSV. Preserve it with the seed sequence, selected preset IDs, cutoff, app revision, and this methodology when preparing a report.

The comparison view offers two saved quick-look references: a one-hour comparison across all five presets and an eight-hour comparison for the baseline preset. The longer horizon is deliberate: the first Mumbai-to-SAT-06 contact opens at 16,033.97 seconds, so the one-hour baseline reference produced no static minimum-hop deliveries. These saved references remain available while a live study runs, but should not be mistaken for results at the live study's selected cutoff. For reportable results, run the selected settings and use that study's downloaded run-level CSV.

Each seed produces a matched pair for each setting: contact-aware earliest-arrival routing and static minimum-hop routing use the same seeded satellite phases, generated contacts, workload, and cutoff. The phase realization uses the versioned SHA-256 transform documented in `experiments.md`; shared satellites keep their phase across controlled preset variants. The dashboard summary is an arithmetic mean across seeds. The CSV retains per-seed results; it is the source for any further dispersion analysis. The current UI does not compute confidence intervals, hypothesis tests, or significance claims.

## Suggested results table

For each preset and policy, report seed count, generated bundles, delivered bundles, mean delivery ratio, mean median-delivery latency, mean hops, expiration ratio, and the number still undelivered at the cutoff. Include the cutoff in every table title or caption. Show contact utilization and mean buffer occupancy as contextual measures, with units and formulas from `experiments.md`.

Use the baseline against each controlled preset to discuss the declared factor. The presets are not a complete factorial design, and comparisons between two non-baseline presets can change multiple factors. Do not generalize beyond the tested settings and seed range.

### Reference run: three seeded phase realizations, 3,600-second cutoff

These are the generated values in `results/reference-study.csv`. Each row averages three matched runs at seeds 42, 43, and 44. Delivery ratio and delivered count are arithmetic means; the delivered-count range shows observed phase variation. Results are illustrative evidence from this simulator run, not a significance test.

| Network setting | Policy | Generated | Mean delivered | Delivered range | Mean delivery ratio |
|---|---|---:|---:|---:|---:|
| Baseline | Contact-aware earliest arrival | 60 | 6.0 | 0–18 | 10.0% |
| Baseline | Static minimum hop | 60 | 0.0 | 0–0 | 0.0% |
| Sparse constellation | Contact-aware earliest arrival | 60 | 1.3 | 0–4 | 2.2% |
| Sparse constellation | Static minimum hop | 60 | 0.0 | 0–0 | 0.0% |
| Limited buffers | Contact-aware earliest arrival | 60 | 0.3 | 0–1 | 0.6% |
| Limited buffers | Static minimum hop | 60 | 0.0 | 0–0 | 0.0% |
| High traffic | Contact-aware earliest arrival | 240 | 6.7 | 0–20 | 2.8% |
| High traffic | Static minimum hop | 240 | 0.0 | 0–0 | 0.0% |
| Expanded constellation | Contact-aware earliest arrival | 60 | 12.3 | 0–30 | 20.6% |
| Expanded constellation | Static minimum hop | 60 | 0.0 | 0–0 | 0.0% |

In this reference sweep, contact-aware earliest-arrival routing delivered some bundles in each setting, while static minimum-hop delivered none by the one-hour cutoff. The largest observed mean delivery ratio was 20.6% for the expanded constellation. The baseline mean was 10.0%. All policies also had pending bundles at cutoff; one hour is shorter than the six-hour bundle TTL. These results support discussion of the tested phase realizations and settings only.

## Interpretation and limits

The cutoff is a measurement boundary, not a claim that pending bundles failed permanently. A pending bundle counts as undelivered at the selected cutoff and remains right-censored; it is not automatically expired. Delivery latency describes delivered bundles only. Explain the selected metric ordering if reporting the dashboard's leader label.

The orbital model uses deterministic circular two-body propagation around a spherical Earth. Contacts are estimated from sampled line of sight and minimum elevation. Sampling may miss short windows; the model does not include an RF link budget, orbital perturbations, fragmentation, custody acknowledgements, or operational constraints. Results are simulator outputs, not predictions of real satellite network performance.

## Report-ready result file

The comparison page's **Download run-level CSV** exports one row for every preset, seed, and routing policy. The file includes preset ID and name, seed, horizon, generated/delivered/source-rejected/expired/undelivered counts, delivery and expiration ratios, median latency in microseconds, mean hops, contact utilization, and mean buffer occupancy in bytes. Keep the original CSV unchanged as the analysis input and record any transformations applied to figures or tables.

The repository also includes a checked-in three-seed reference run at [`results/reference-study.csv`](results/reference-study.csv) and its JSON companion. Regenerate both from the repository root with `backend/.venv/Scripts/python.exe backend/scripts/run_reference_study.py` on Windows (`backend/.venv/bin/python` on Unix). The script runs all five presets at seed 42–44 and a 3,600-second cutoff using the same paired policy comparison as the API.

## Five-seed controlled evaluation

The expanded controlled evaluation compares both routing policies on all five selectable presets with shared seeded satellite phases, seeds 42–46, and a 3,600-second (1-hour) observation cutoff. It adds two phase realizations to the included three-seed reference set. Each preset isolates a declared setting relative to baseline, but the one-hour cutoff is shorter than the first Mumbai-to-SAT-06 contact at 16,033.97 seconds. As a result, static-minimum-hop outcomes are heavily right-censored in this comparison. The saved eight-hour baseline comparison provides a separate view at a longer cutoff; do not compare the one-hour preset results directly with its eight-hour outcomes as if only one factor changed.

The five-seed run-level dataset is [`results/final-evaluation.csv`](results/final-evaluation.csv), with a JSON manifest and full row values in [`results/final-evaluation.json`](results/final-evaluation.json). Regenerate it from the repository root with `backend/.venv/Scripts/python.exe backend/scripts/run_final_evaluation.py` on Windows (`backend/.venv/bin/python` on Unix). Each row records one preset, seed, and routing policy, including generated, delivered, rejected, expired, and undelivered counts plus latency, hops, utilization, and occupancy. The study is descriptive across five deterministic phase realizations; it is not a statistical significance test.

### Five-seed one-hour summary

| Network setting | Policy | Attempted per run | Mean delivered (range) | Mean delivery ratio |
|---|---|---:|---:|---:|
| Baseline | Contact-aware earliest arrival | 60 | 3.6 (0–18) | 6.0% |
| Baseline | Static minimum hop | 60 | 0.0 (0–0) | 0.0% |
| Sparse constellation | Contact-aware earliest arrival | 60 | 0.8 (0–4) | 1.3% |
| Sparse constellation | Static minimum hop | 60 | 0.0 (0–0) | 0.0% |
| Limited buffers | Contact-aware earliest arrival | 60 | 0.2 (0–1) | 0.3% |
| Limited buffers | Static minimum hop | 60 | 0.0 (0–0) | 0.0% |
| High traffic | Contact-aware earliest arrival | 240 | 4.0 (0–20) | 1.7% |
| High traffic | Static minimum hop | 240 | 0.0 (0–0) | 0.0% |
| Expanded constellation | Contact-aware earliest arrival | 60 | 19.6 (0–32) | 32.7% |
| Expanded constellation | Static minimum hop | 60 | 0.0 (0–0) | 0.0% |

The expanded constellation had the largest contact-aware mean delivery ratio in these tested realizations. The one-hour cutoff precedes the first contact used by the static minimum-hop baseline, so its zeros here describe the observation window, not eventual delivery. These averages and ranges describe five seeds only and do not establish statistical significance.
