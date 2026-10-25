"""Regenerate the five-seed, one-hour controlled evaluation dataset."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from leo_dtn.experiments import ENGINE_VERSION, compare_routing_policies  # noqa: E402
from leo_dtn.scenarios import scenario_catalog  # noqa: E402

HORIZON_US = 3_600_000_000
SEEDS = (42, 43, 44, 45, 46)
SCENARIO_IDS = (
    "leo-mumbai-new-york",
    "leo-sparse-constellation",
    "leo-limited-buffers",
    "leo-high-traffic",
    "leo-expanded-constellation",
)
OUTPUT = ROOT / "docs" / "results"


def main() -> None:
    scenarios = {item.scenario_id: item for item in scenario_catalog()}
    rows: list[dict[str, object]] = []
    for scenario_id in SCENARIO_IDS:
        scenario = scenarios[scenario_id]
        for seed in SEEDS:
            print(f"Running {scenario_id}, seed {seed}…", flush=True)
            results = compare_routing_policies(
                scenario=scenario,
                random_seed=seed,
                horizon_us=HORIZON_US,
            )
            for result in results:
                report = result.metrics
                rows.append({
                    "scenario_id": scenario_id,
                    "scenario_name": scenario.name,
                    "seed": seed,
                    "horizon_seconds": HORIZON_US / 1_000_000,
                    "routing_policy": result.routing_policy,
                    "generated_count": report.generated_count,
                    "delivered_count": report.delivered_count,
                    "undelivered_count": report.undelivered_count,
                    "source_rejected_count": report.source_rejected_count,
                    "expired_count": report.expired_count,
                    "delivery_ratio": report.delivery_ratio,
                    "expiration_ratio": report.expiration_ratio,
                    "median_delivery_latency_us": report.median_delivery_latency_us,
                    "mean_hop_count": report.mean_hop_count,
                    "contact_utilization_fraction": report.contact_utilization_fraction,
                    "mean_total_buffer_occupancy_bytes": report.mean_total_buffer_occupancy_bytes,
                })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT / "final-evaluation.csv"
    fields = list(rows[0])
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    json_path = OUTPUT / "final-evaluation.json"
    json_path.write_text(
        json.dumps({
            "study": "LEO-DTN five-seed controlled evaluation",
            "engine_version": ENGINE_VERSION,
            "horizon_us": HORIZON_US,
            "seeds": SEEDS,
            "scenario_ids": SCENARIO_IDS,
            "normalized_scenarios": {
                scenario_id: {
                    "name": scenarios[scenario_id].name,
                    "description": scenarios[scenario_id].description,
                    "focus": scenarios[scenario_id].focus,
                    "nodes": [asdict(node) for node in scenarios[scenario_id].nodes],
                    "contacts": [asdict(contact) for contact in scenarios[scenario_id].contacts],
                    "bundles": [asdict(bundle) for bundle in scenarios[scenario_id].bundles],
                    "orbital_contact_generation": scenarios[scenario_id].orbital_contact_generation,
                    "contact_sample_interval_us": scenarios[scenario_id].contact_sample_interval_us,
                    "minimum_elevation_deg": scenarios[scenario_id].minimum_elevation_deg,
                    "orbital_link_rate_bits_per_second": scenarios[scenario_id].orbital_link_rate_bits_per_second,
                    "bundle_generation_interval_us": scenarios[scenario_id].bundle_generation_interval_us,
                }
                for scenario_id in SCENARIO_IDS
            },
            "routing_policies": ["contact_aware_earliest_arrival", "static_minimum_hop"],
            "orbital_model": "circular two-body propagation around a spherical Earth with sampled line-of-sight and minimum-elevation contacts",
            "replication_note": "Five deterministic paired phase realizations for each controlled preset; descriptive results only, no significance test.",
            "rows": rows,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {csv_path.relative_to(ROOT)} and {json_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
