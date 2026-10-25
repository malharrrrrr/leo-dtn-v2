from leo_dtn.engine import SimulationEngine
from leo_dtn.model import (
    BundleRequest,
    BundleStatus,
    Contact,
    ContactInterruption,
    Node,
    NodeKind,
)
from leo_dtn.routing import StaticMinimumHop
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


def test_contact_interruption_discards_partial_bits_and_restarts_later():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (
        Contact("first", "A", "B", 0, 10 * SECOND, 8_000),
        Contact("later", "A", "B", 20 * SECOND, 30 * SECOND, 8_000),
    )
    engine = SimulationEngine(
        nodes=nodes,
        contacts=contacts,
        interruptions=(ContactInterruption("first", SECOND // 2),),
    )
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 100 * SECOND))

    snapshot = engine.run_until(22 * SECOND)

    assert snapshot.bundles[0].status == BundleStatus.DELIVERED
    assert [hop.transmission_start_us for hop in snapshot.bundles[0].forwarding_history] == [
        20 * SECOND
    ]
    interrupted = next(event for event in snapshot.events if event.kind == "transmission_interrupted")
    assert interrupted.time_us == SECOND // 2
    assert dict(interrupted.details)["discarded_partial_bits"] == "4000"
    assert next(node.buffer_occupancy_bytes for node in snapshot.nodes if node.node.node_id == "A") == 0


def test_bundles_contend_serially_for_a_contact_in_deterministic_order():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (Contact("A-B", "A", "B", 0, 3 * SECOND, 8_000),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("second", "A", "B", 1_000, 0, 10 * SECOND))
    engine.add_bundle(BundleRequest("first", "A", "B", 1_000, 0, 10 * SECOND))

    snapshot = engine.run_until(3 * SECOND)

    starts = [event for event in snapshot.events if event.kind == "transmission_started"]
    assert [(event.bundle_id, event.time_us) for event in starts] == [
        ("first", 0),
        ("second", SECOND),
    ]
    assert all(bundle.status == BundleStatus.DELIVERED for bundle in snapshot.bundles)


def test_receiver_buffer_overflow_keeps_bundle_at_sender():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 500),
    )
    contacts = (Contact("A-B", "A", "B", 0, 3 * SECOND, 8_000),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 10 * SECOND))

    snapshot = engine.run_until(2 * SECOND)

    assert snapshot.bundles[0].status == BundleStatus.QUEUED
    assert snapshot.bundles[0].holder == "A"
    assert next(node.buffer_occupancy_bytes for node in snapshot.nodes if node.node.node_id == "A") == 1_000
    assert any(event.kind == "receiver_buffer_rejected" for event in snapshot.events)


def test_expiration_while_queued_releases_buffer_capacity():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    engine = SimulationEngine(nodes=nodes, contacts=())
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, SECOND))

    snapshot = engine.run_until(SECOND)

    assert snapshot.bundles[0].status == BundleStatus.EXPIRED
    assert next(node.buffer_occupancy_bytes for node in snapshot.nodes if node.node.node_id == "A") == 0


def test_expiration_during_transmission_invalidates_completion_and_releases_contact():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (Contact("A-B", "A", "B", 0, 3 * SECOND, 8_000),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, SECOND // 2))

    snapshot = engine.run_until(2 * SECOND)

    assert snapshot.bundles[0].status == BundleStatus.EXPIRED
    assert snapshot.active_transmissions == ()
    assert not any(event.kind == "bundle_delivered" for event in snapshot.events)


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


def test_contact_must_remain_open_until_last_bit_arrives():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    # One second to serialize plus one second of propagation lands exactly at
    # the half-open contact end, so this route is infeasible.
    contacts = (Contact("A-B", "A", "B", 0, 2 * SECOND, 8_000, SECOND),)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 10 * SECOND))

    snapshot = engine.run_until(2 * SECOND)

    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.QUEUED
    assert bundle.holder == "A"
    assert bundle.forwarding_history == ()
    assert not any(event.kind == "transmission_started" for event in snapshot.events)


def test_contact_interruption_during_propagation_fails_and_retries_from_sender():
    nodes = (
        Node("A", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (
        Contact("first", "A", "B", 0, 5 * SECOND, 8_000, 2 * SECOND),
        Contact("retry", "A", "B", 5 * SECOND, 7 * SECOND, 8_000),
    )
    engine = SimulationEngine(
        nodes=nodes,
        contacts=contacts,
        interruptions=(ContactInterruption("first", 1_500_000),),
    )
    engine.add_bundle(BundleRequest("B1", "A", "B", 1_000, 0, 10 * SECOND))

    snapshot = engine.run_until(6 * SECOND)

    bundle = snapshot.bundles[0]
    assert bundle.status == BundleStatus.DELIVERED
    assert bundle.forwarding_history[0].contact_id == "retry"
    assert bundle.forwarding_history[0].transmission_start_us == 5 * SECOND
    failed = next(
        event for event in snapshot.events
        if event.kind == "transmission_interrupted" and event.contact_id == "first"
    )
    assert dict(failed.details) == {
        "failure_reason": "contact_ended_before_arrival",
        "arrival_time_us": str(3 * SECOND),
    }


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


def test_recurring_bundle_stream_generates_deterministic_bundle_ids():
    nodes = (Node("A", NodeKind.GROUND_STATION, 10_000), Node("B", NodeKind.GROUND_STATION, 10_000))
    engine = SimulationEngine(nodes=nodes, contacts=())
    engine.add_recurring_bundle(
        BundleRequest("TRAFFIC", "A", "B", 100, 0, 100_000_000),
        interval_us=10,
    )

    snapshot = engine.run_until(25)
    assert [bundle.bundle_id for bundle in snapshot.bundles] == [
        "TRAFFIC", "TRAFFIC-AUTO-000002", "TRAFFIC-AUTO-000003",
    ]
    assert [event.bundle_id for event in snapshot.events if event.kind == "bundle_generated"] == [
        "TRAFFIC", "TRAFFIC-AUTO-000002", "TRAFFIC-AUTO-000003",
    ]


def test_newly_planned_contact_start_wakes_bundle_waiting_at_relay():
    nodes = (
        Node("RELAY", NodeKind.SATELLITE, 2_000),
        Node("DEST", NodeKind.GROUND_STATION, 2_000),
    )
    engine = SimulationEngine(nodes=nodes, contacts=())
    engine.add_bundle(BundleRequest("B1", "RELAY", "DEST", 1_000, 0, 100 * SECOND))
    at_relay = engine.run_until(3 * SECOND)
    assert at_relay.bundles[0].status == BundleStatus.QUEUED
    assert at_relay.bundles[0].holder == "RELAY"

    engine.extend_contact_plan((Contact("RELAY-DEST", "RELAY", "DEST", 5 * SECOND, 10 * SECOND, 8_000),))
    delivered = engine.run_until(7 * SECOND)

    assert delivered.bundles[0].status == BundleStatus.DELIVERED
    assert [hop.transmission_start_us for hop in delivered.bundles[0].forwarding_history] == [5 * SECOND]


def test_routing_policy_is_replaceable_without_changing_event_execution():
    nodes = (
        Node("S", NodeKind.GROUND_STATION, 2_000),
        Node("B", NodeKind.SATELLITE, 2_000),
        Node("D", NodeKind.GROUND_STATION, 2_000),
    )
    contacts = (
        Contact("direct-late", "S", "D", 100 * SECOND, 102 * SECOND, 8_000),
        Contact("first-hop", "S", "B", 0, 2 * SECOND, 8_000),
        Contact("second-hop", "B", "D", 2 * SECOND, 4 * SECOND, 8_000),
    )
    engine = SimulationEngine(nodes=nodes, contacts=contacts, routing_policy=StaticMinimumHop())
    engine.add_bundle(BundleRequest("B1", "S", "D", 1_000, 0, 200 * SECOND))

    snapshot = engine.run_until(102 * SECOND)

    assert snapshot.routing_policy == "static_minimum_hop"
    assert snapshot.bundles[0].status == BundleStatus.DELIVERED
    assert snapshot.bundles[0].forwarding_history[0].contact_id == "direct-late"
    assert snapshot.bundles[0].forwarding_history[0].receiver_acceptance_us == 101 * SECOND

    time_aware = SimulationEngine(nodes=nodes, contacts=contacts)
    time_aware.add_bundle(BundleRequest("B1", "S", "D", 1_000, 0, 200 * SECOND))
    faster_snapshot = time_aware.run_until(4 * SECOND)
    assert faster_snapshot.routing_policy == "contact_aware_earliest_arrival"
    assert faster_snapshot.bundles[0].status == BundleStatus.DELIVERED
    assert [hop.contact_id for hop in faster_snapshot.bundles[0].forwarding_history] == [
        "first-hop",
        "second-hop",
    ]
    assert faster_snapshot.bundles[0].forwarding_history[-1].receiver_acceptance_us == 3 * SECOND
