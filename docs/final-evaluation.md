# Final evaluation guide

## Study question

How do contact availability, buffer capacity, and routing strategy affect bundle delivery performance in this simplified LEO network model?

## Reproduce the dashboard comparison

1. Start the local API and dashboard using the commands in `README.md`.
2. Open **Metrics & comparison**. The baseline preset is selected for the starter run.
3. Keep the default observation cutoff at 3,600 seconds for the reference comparison. Set a starting seed and choose 3 or 5 consecutive seeds for a descriptive repeat.
4. Run the baseline pair, then add one controlled preset at a time: sparse constellation, limited buffers, high traffic, or expanded constellation.
5. Download the run-level CSV. Preserve it with the seed sequence, selected preset IDs, cutoff, app revision, and this methodology when preparing a report.

The comparison view also offers a saved quick-look reference for the baseline preset using seeds 42–46 at a 28,800-second (8-hour) cutoff. This longer horizon is deliberate: the first Mumbai-to-SAT-06 contact opens at 16,033.97 seconds, so the one-hour live-study limit produced no static minimum-hop deliveries. The saved reference remains available while a live study runs, but should not be mistaken for results at the live study's selected cutoff. For reportable results, run the selected settings and use that study's downloaded run-level CSV.

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
