from leo_dtn.engine import SimulationEngine
from leo_dtn.model import BundleStatus
from leo_dtn.scenarios import SECOND, relay_vertical_slice_inputs, scenario_catalog


def presets_by_id():
    return {preset.scenario_id: preset for preset in scenario_catalog()}


def test_every_selectable_preset_uses_moving_geometry_derived_leo_contacts():
    for preset in scenario_catalog():
        assert preset.orbital_contact_generation
        assert preset.contacts == ()
        assert all(node.orbit is not None for node in preset.nodes if node.kind.value == "satellite")
        assert sum(node.kind.value == "ground_station" for node in preset.nodes) == 2
        assert {node.node_id for node in preset.nodes if node.kind.value == "ground_station"} == {
            "GS-MUMBAI", "GS-NEW-YORK",
        }


def test_leo_presets_keep_the_default_simulation_as_the_baseline():
    presets = presets_by_id()
    baseline = presets["leo-mumbai-new-york"]
    assert baseline.name == "Mumbai–New York · baseline"
    assert len(baseline.nodes) == 10
    assert len([node for node in baseline.nodes if node.orbit is not None]) == 8
    assert baseline.bundles[0].bundle_id == "BND-001"
    assert baseline.bundles[0].payload_bytes == 50_000_000
    assert baseline.bundle_generation_interval_us == 60 * SECOND
    assert baseline.bundles[0].ttl_us == 6 * 60 * 60 * SECOND


def test_sparse_buffer_traffic_and_expanded_presets_each_change_only_their_focus():
    presets = presets_by_id()
    baseline = presets["leo-mumbai-new-york"]
    sparse = presets["leo-sparse-constellation"]
    limited = presets["leo-limited-buffers"]
    traffic = presets["leo-high-traffic"]
    expanded = presets["leo-expanded-constellation"]

    assert sum(node.orbit is not None for node in sparse.nodes) == 4
    assert sparse.bundles == baseline.bundles
    assert sparse.bundle_generation_interval_us == baseline.bundle_generation_interval_us

    baseline_satellite_buffers = {node.buffer_capacity_bytes for node in baseline.nodes if node.orbit is not None}
    limited_satellite_buffers = {node.buffer_capacity_bytes for node in limited.nodes if node.orbit is not None}
    assert baseline_satellite_buffers == {10_000_000_000}
    assert limited_satellite_buffers == {50_000_000}
    assert limited.bundles == baseline.bundles

    assert traffic.bundles[0].payload_bytes == 100_000_000
    assert traffic.bundle_generation_interval_us == 15 * SECOND
    assert traffic.nodes == baseline.nodes

    assert sum(node.orbit is not None for node in expanded.nodes) == 16
    assert expanded.bundles == baseline.bundles
    assert expanded.bundle_generation_interval_us == baseline.bundle_generation_interval_us


def test_hand_checkable_relay_fixture_still_proves_store_carry_forward():
    nodes, contacts, bundles = relay_vertical_slice_inputs()
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(bundles[0])
    snapshot = engine.run_until(30 * SECOND)
    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.DELIVERED
    assert [hop.receiver_acceptance_us for hop in bundle.forwarding_history] == [3 * SECOND, 21 * SECOND]
