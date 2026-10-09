from leo_dtn.experiments import run_experiment
from leo_dtn.metrics import calculate_metrics
from leo_dtn.model import Node
from leo_dtn.scenarios import SECOND, relay_vertical_slice, relay_vertical_slice_inputs


def test_metrics_match_hand_calculated_delivery_and_buffer_values():
    snapshot = relay_vertical_slice().run_until(22 * SECOND)

    metrics = calculate_metrics(snapshot, horizon_us=22 * SECOND)

    assert metrics.generated_count == 1
    assert metrics.delivered_count == 1
    assert metrics.undelivered_count == 0
    assert metrics.delivery_ratio == 1
    assert metrics.mean_delivery_latency_us == 19 * SECOND
    assert metrics.mean_hop_count == 2
    assert metrics.expired_count == 0
    assert metrics.peak_total_buffer_occupancy_bytes == 1_000
    # The relay retains the bundle through serialization and releases it at acceptance.
    assert metrics.mean_total_buffer_occupancy_bytes == 19_000_000_000 / (22 * SECOND)
    assert metrics.per_contact_utilization[0].utilization_fraction == 0.1
    assert metrics.per_contact_utilization[1].utilization_fraction == 0.5
    assert metrics.contact_utilization_fraction == 1 / 6


def test_horizon_undelivered_is_not_mislabeled_expired():
    snapshot = relay_vertical_slice().run_until(5 * SECOND)

    metrics = calculate_metrics(snapshot, horizon_us=5 * SECOND)

    assert metrics.generated_count == 1
    assert metrics.delivered_count == 0
    assert metrics.undelivered_count == 1
    assert metrics.expired_count == 0
    assert metrics.status_counts == (
        ("queued", 1),
        ("transmitting", 0),
        ("in_transit", 0),
        ("delivered", 0),
        ("expired", 0),
        ("rejected_at_source", 0),
    )


def test_source_rejection_stays_in_delivery_denominator():
    nodes, contacts, bundles = relay_vertical_slice_inputs()
    nodes = (Node("GS-A", nodes[0].kind, 10), *nodes[1:])
    result = run_experiment(
        scenario_id="source-overflow",
        random_seed=12,
        horizon_us=5 * SECOND,
        nodes=nodes,
        contacts=contacts,
        bundles=bundles,
    )

    assert result.metrics.generated_count == 1
    assert result.metrics.source_rejected_count == 1
    assert result.metrics.delivery_ratio == 0
    assert result.metrics.expiration_ratio == 0


def test_empty_run_has_undefined_delivery_and_expiration_ratios():
    nodes, contacts, _ = relay_vertical_slice_inputs()
    result = run_experiment(
        scenario_id="empty",
        random_seed=0,
        horizon_us=SECOND,
        nodes=nodes,
        contacts=contacts,
        bundles=(),
    )

    assert result.metrics.generated_count == 0
    assert result.metrics.delivery_ratio is None
    assert result.metrics.expiration_ratio is None
    assert result.metrics.mean_total_buffer_occupancy_bytes == 0


def test_metric_horizon_must_match_snapshot_time():
    snapshot = relay_vertical_slice().run_until(5 * SECOND)

    try:
        calculate_metrics(snapshot, horizon_us=4 * SECOND)
    except ValueError as exc:
        assert "match the snapshot" in str(exc)
    else:
        raise AssertionError("metrics must not mix a cutoff with a later snapshot")
