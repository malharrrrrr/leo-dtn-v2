from leo_dtn.engine import SimulationEngine
from leo_dtn.model import BundleRequest, BundleStatus, Contact, Node, NodeKind
from leo_dtn.scenarios import SECOND, relay_vertical_slice


def test_store_carry_forward_vertical_slice_has_expected_times():
    engine = relay_vertical_slice()

    snapshot = engine.run_until(22 * SECOND)

    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.DELIVERED
    assert bundle.forwarding_history[0].transmission_start_us == 2 * SECOND
    assert bundle.forwarding_history[0].serialization_complete_us == 3 * SECOND
    assert bundle.forwarding_history[0].receiver_acceptance_us == 3 * SECOND
    assert bundle.forwarding_history[1].transmission_start_us == 20 * SECOND
    assert bundle.forwarding_history[1].serialization_complete_us == 21 * SECOND
    assert bundle.forwarding_history[1].receiver_acceptance_us == 21 * SECOND
    assert [event.kind for event in snapshot.events if event.kind.startswith("transmission_")] == [
        "transmission_started",
        "transmission_completed",
        "transmission_started",
        "transmission_completed",
    ]
    relay_occupancy = next(node.buffer_occupancy_bytes for node in snapshot.nodes if node.node.node_id == "SAT-R")
    assert relay_occupancy == 0


def test_bundle_waits_in_relay_buffer_until_second_contact():
    engine = relay_vertical_slice()

    at_five = engine.run_until(5 * SECOND)

    bundle = at_five.bundles[0]
    assert bundle.status == BundleStatus.QUEUED
    assert bundle.holder == "SAT-R"
    assert len(bundle.forwarding_history) == 1
    assert next(node.buffer_occupancy_bytes for node in at_five.nodes if node.node.node_id == "SAT-R") == 1_000


def test_snapshot_exposes_real_active_transmission_for_visualization():
    engine = relay_vertical_slice()
    for _ in range(3):
        engine.step()

    snapshot = engine.snapshot()

    assert snapshot.time_us == 2 * SECOND
    assert len(snapshot.contacts) == 2
    assert snapshot.active_transmissions[0].bundle_id == "B1"
    assert snapshot.active_transmissions[0].contact_id == "C-A-R"
    assert snapshot.active_transmissions[0].start_time_us == 2 * SECOND
    assert snapshot.active_transmissions[0].serialization_complete_us == 3 * SECOND


def test_unavailable_contact_cannot_carry_bundle():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    engine = SimulationEngine(nodes=nodes, contacts=())
    engine.add_bundle(BundleRequest("B1", "A", "B", 100, 0, 10 * SECOND))

    snapshot = engine.run_until(5 * SECOND)

    assert snapshot.bundles[0].status == BundleStatus.QUEUED
    assert snapshot.bundles[0].holder == "A"
    assert not any(event.kind == "bundle_delivered" for event in snapshot.events)


def test_transmission_must_finish_strictly_before_contact_closes():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    # A 1,000-byte bundle needs exactly one second at 8,000 bit/s.
    contacts = (Contact("A-B", "A", "B", 0, SECOND, 8_000),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 10 * SECOND))

    snapshot = engine.run_until(SECOND)

    assert snapshot.bundles[0].status == BundleStatus.QUEUED
    assert not any(event.kind == "transmission_started" for event in snapshot.events)


def test_source_buffer_rejects_bundle_without_creating_a_holder():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 50),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    engine = SimulationEngine(nodes=nodes, contacts=())
    engine.add_bundle(BundleRequest("B1", "A", "B", 100, 0, 10 * SECOND))

    snapshot = engine.run_until(0)

    assert snapshot.bundles[0].status == BundleStatus.REJECTED_AT_SOURCE
    assert snapshot.bundles[0].holder is None
    assert any(event.kind == "bundle_rejected_at_source" for event in snapshot.events)


def test_propagation_delay_is_separate_from_serialization():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (Contact("A-B", "A", "B", 0, 5 * SECOND, 8_000, 2 * SECOND),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 10 * SECOND))

    snapshot = engine.run_until(3 * SECOND)

    hop = snapshot.bundles[0].forwarding_history[0]
    assert hop.serialization_complete_us == SECOND
    assert hop.receiver_acceptance_us == 3 * SECOND
    assert snapshot.bundles[0].status == BundleStatus.DELIVERED


def test_expiration_precedes_arrival_at_same_timestamp():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (Contact("A-B", "A", "B", 0, 4 * SECOND, 8_000, 2 * SECOND),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 3 * SECOND))

    snapshot = engine.run_until(3 * SECOND)

    assert snapshot.bundles[0].status == BundleStatus.EXPIRED
    assert not any(event.kind == "bundle_delivered" for event in snapshot.events)


def test_equal_timestamp_events_follow_priority_then_insertion_order():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    engine = SimulationEngine(nodes=nodes, contacts=())
    # Two generation events at the same timestamp are processed in insertion order.
    engine.add_bundle(BundleRequest("first", "A", "B", 100, 0, 10 * SECOND))
    engine.add_bundle(BundleRequest("second", "A", "B", 100, 0, 10 * SECOND))

    snapshot = engine.run_until(0)
    generated = [event.bundle_id for event in snapshot.events if event.kind == "bundle_generated"]
    assert generated == ["first", "second"]


def test_invalid_overlapping_contacts_are_rejected():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (
        Contact("one", "A", "B", 0, 10, 8_000),
        Contact("two", "A", "B", 9, 20, 8_000),
    )
    try:
        SimulationEngine(nodes=nodes, contacts=contacts)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("overlapping directed contacts should be rejected")


def test_identical_scenarios_replay_identically():
    first = relay_vertical_slice().run_until(22 * SECOND)
    second = relay_vertical_slice().run_until(22 * SECOND)

    assert first == second
