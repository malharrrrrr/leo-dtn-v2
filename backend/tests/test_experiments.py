import csv
import json

from leo_dtn.experiments import (
    export_events_csv,
    export_metrics_csv,
    export_run_json,
    export_scenario_csv,
    run_experiment,
)
from leo_dtn.model import ContactInterruption
from leo_dtn.routing import StaticMinimumHop
from leo_dtn.scenarios import SECOND, relay_vertical_slice_inputs


def _run(*, interruptions=()):
    nodes, contacts, bundles = relay_vertical_slice_inputs()
    return run_experiment(
        scenario_id="relay-vertical-slice",
        random_seed=7,
        horizon_us=22 * SECOND,
        nodes=nodes,
        contacts=contacts,
        bundles=bundles,
        interruptions=interruptions,
    )


def test_manifest_captures_seed_normalized_config_and_run_cutoff():
    result = _run()

    manifest = result.manifest
    configuration = json.loads(manifest.normalized_configuration_json)
    assert manifest.schema_version == 1
    assert manifest.random_seed == 7
    assert manifest.run_status == "completed_to_horizon"
    assert manifest.routing_policy == "contact_aware_earliest_arrival"
    assert len(configuration["nodes"]) == 3
    assert len(configuration["contacts"]) == 2
    assert len(configuration["bundles"]) == 1


def test_identical_run_inputs_produce_identical_exports():
    assert export_run_json(_run()) == export_run_json(_run())
    assert export_events_csv(_run()) == export_events_csv(_run())
    assert export_metrics_csv(_run()) == export_metrics_csv(_run())


def test_csv_exports_include_scenario_events_and_metrics():
    result = _run()

    scenario_rows = list(csv.DictReader(export_scenario_csv(result).splitlines()))
    event_rows = list(csv.DictReader(export_events_csv(result).splitlines()))
    metric_rows = list(csv.DictReader(export_metrics_csv(result).splitlines()))

    assert [row["record_type"] for row in scenario_rows].count("node") == 3
    assert [row["record_type"] for row in scenario_rows].count("contact") == 2
    assert [row["record_type"] for row in scenario_rows].count("bundle") == 1
    assert any(row["kind"] == "bundle_delivered" for row in event_rows)
    assert any(row["metric"] == "delivery_ratio" for row in metric_rows)
    assert all(value is not None for row in scenario_rows for value in row.values())


def test_manifest_and_scenario_csv_keep_interruption_inputs():
    interruption = ContactInterruption("C-A-R", 5 * SECOND)
    result = _run(interruptions=(interruption,))

    config = json.loads(result.manifest.normalized_configuration_json)
    scenario_rows = list(csv.DictReader(export_scenario_csv(result).splitlines()))
    interruption_row = next(row for row in scenario_rows if row["record_type"] == "interruption")

    assert config["interruptions"] == [{"contact_id": "C-A-R", "time_us": 5 * SECOND}]
    assert interruption_row["id"] == "C-A-R"
    assert interruption_row["interruption_time_us"] == str(5 * SECOND)


def test_selected_routing_policy_is_recorded_with_experiment():
    nodes, contacts, bundles = relay_vertical_slice_inputs()
    result = run_experiment(
        scenario_id="relay-static-baseline",
        random_seed=3,
        horizon_us=22 * SECOND,
        nodes=nodes,
        contacts=contacts,
        bundles=bundles,
        routing_policy=StaticMinimumHop(),
    )

    assert result.manifest.routing_policy == "static_minimum_hop"
    config = json.loads(result.manifest.normalized_configuration_json)
    assert config["routing_policy"] == "static_minimum_hop"
