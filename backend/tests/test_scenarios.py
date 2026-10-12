from leo_dtn.engine import SimulationEngine
from leo_dtn.model import BundleStatus
from leo_dtn.scenarios import SECOND, scenario_catalog


def run_preset(scenario_id: str):
    preset = next(item for item in scenario_catalog() if item.scenario_id == scenario_id)
    assert not preset.orbital_contact_generation
    engine = SimulationEngine(nodes=preset.nodes, contacts=preset.contacts)
    for bundle in preset.bundles:
        engine.add_bundle(bundle)
    return engine.run_until(60 * SECOND)


def test_direct_contact_preset_delivers_without_relay():
    snapshot = run_preset("direct-contact-baseline")
    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.DELIVERED
    assert len(bundle.forwarding_history) == 1


def test_store_and_forward_preset_retains_bundle_between_contacts():
    snapshot = run_preset("relay-vertical-slice")
    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.DELIVERED
    assert [hop.receiver_acceptance_us for hop in bundle.forwarding_history] == [3 * SECOND, 21 * SECOND]


def test_multi_hop_preset_forwards_through_both_relays():
    snapshot = run_preset("intermittent-multi-hop")
    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.DELIVERED
    assert [hop.to_node for hop in bundle.forwarding_history] == ["SAT-R1", "SAT-R2", "GS-B"]


def test_buffer_pressure_preset_rejects_second_bundle_at_source_capacity():
    snapshot = run_preset("relay-buffer-pressure")
    statuses = {bundle.bundle_id: bundle.status for bundle in snapshot.bundles}
    assert statuses["BND-PRESS-1"] == BundleStatus.DELIVERED
    assert statuses["BND-PRESS-2"] == BundleStatus.REJECTED_AT_SOURCE


def test_moving_leo_preset_has_orbits_and_geometry_generated_contacts():
    preset = next(item for item in scenario_catalog() if item.scenario_id == "leo-mumbai-new-york")
    assert preset.orbital_contact_generation
    assert len([node for node in preset.nodes if node.orbit is not None]) == 8
    assert preset.contacts == ()
    assert preset.bundles[0].source == "GS-MUMBAI"
    assert preset.bundles[0].destination == "GS-NEW-YORK"
