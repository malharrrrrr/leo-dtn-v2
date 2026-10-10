import math

from leo_dtn.model import BundleRequest, CircularOrbit, Node, NodeKind
from leo_dtn.orbit import generate_contact_plan, position_and_velocity_ecef, visible


def ground_position(latitude: float, longitude: float) -> tuple[float, float, float]:
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    return (
        6371 * math.cos(lat) * math.cos(lon),
        6371 * math.cos(lat) * math.sin(lon),
        6371 * math.sin(lat),
    )


def test_circular_orbit_position_moves_deterministically_and_stays_at_altitude():
    node = Node("SAT-1", NodeKind.SATELLITE, 1000, orbit=CircularOrbit(550, 53, 27, 10))
    position0, velocity0 = position_and_velocity_ecef(node, 0)
    position1, velocity1 = position_and_velocity_ecef(node, 60_000_000)
    assert position0 is not None and position1 is not None
    assert velocity0 is not None and velocity1 is not None
    assert position0 != position1
    assert math.isclose(math.sqrt(sum(value * value for value in position0)), 6371 + 550, abs_tol=1e-8)
    assert 7.0 < math.sqrt(sum(value * value for value in velocity0)) < 7.7
    assert position1 == position_and_velocity_ecef(node, 60_000_000)[0]


def test_ground_station_visibility_creates_and_closes_real_contact_windows():
    station = Node("GS", NodeKind.GROUND_STATION, 1000, (6371.0, 0.0, 0.0))
    satellite = Node("SAT", NodeKind.SATELLITE, 1000, orbit=CircularOrbit(500, 0, 0, 0))
    assert visible(station, satellite, 0)
    contacts = generate_contact_plan(
        (station, satellite), horizon_us=3_000_000_000,
        sample_interval_us=5_000_000, rate_bits_per_second=1_000_000,
        minimum_elevation_deg=10,
    )
    assert contacts
    assert len(contacts) == 2
    assert contacts[0].from_node != contacts[0].to_node
    assert contacts[0].start_us == contacts[1].start_us
    assert contacts[0].end_us == contacts[1].end_us
    assert contacts[0].end_us < 3_000_000_000


def test_orbital_contact_plan_is_repeatable_and_respects_visibility():
    station = Node("GS", NodeKind.GROUND_STATION, 1000, (6371.0, 0.0, 0.0))
    satellite = Node("SAT", NodeKind.SATELLITE, 1000, orbit=CircularOrbit(500, 0, 0, 0))
    args = dict(horizon_us=10_000_000_000, sample_interval_us=5_000_000)
    first = generate_contact_plan((station, satellite), **args)
    second = generate_contact_plan((station, satellite), **args)
    assert first == second
    assert first and all(contact.end_us <= args["horizon_us"] for contact in first)


def test_no_generated_contact_for_nodes_without_visibility_or_orbit():
    station_a = Node("GS-A", NodeKind.GROUND_STATION, 1000, (6371.0, 0.0, 0.0))
    station_b = Node("GS-B", NodeKind.GROUND_STATION, 1000, (0.0, 6371.0, 0.0))
    assert generate_contact_plan((station_a, station_b), horizon_us=30_000_000) == ()


def test_moving_positions_are_exposed_by_engine_snapshots():
    from leo_dtn.engine import SimulationEngine

    satellite = Node("SAT", NodeKind.SATELLITE, 1000, orbit=CircularOrbit(550, 53, 27, 10))
    destination = Node("GS", NodeKind.GROUND_STATION, 1000, (6371.0, 0.0, 0.0))
    engine = SimulationEngine(nodes=(satellite, destination), contacts=())
    initial_snapshot = engine.snapshot()
    initial = next(item.position_km for item in initial_snapshot.nodes if item.node.node_id == "GS")
    initial_satellite = next(item.position_km for item in initial_snapshot.nodes if item.node.node_id == "SAT")
    later_snapshot = engine.run_until(60_000_000)
    later = next(item.position_km for item in later_snapshot.nodes if item.node.node_id == "GS")
    later_satellite = next(item.position_km for item in later_snapshot.nodes if item.node.node_id == "SAT")
    # Static ground station is fixed; the engine time still advances via the requested horizon.
    assert later == initial
    assert initial_satellite != later_satellite


def test_default_demo_orbits_cover_both_ground_stations_at_start():
    from leo_dtn.orbit import EARTH_RADIUS_KM

    mumbai = Node("GS-MUMBAI", NodeKind.GROUND_STATION, 1000, ground_position(19.076, 72.878))
    new_york = Node("GS-NEW-YORK", NodeKind.GROUND_STATION, 1000, ground_position(40.7128, -74.006))
    sat_mumbai = Node("SAT-M", NodeKind.SATELLITE, 1000, orbit=CircularOrbit(550, 53, 59, 22))
    sat_singapore = Node("SAT-S", NodeKind.SATELLITE, 1000, orbit=CircularOrbit(550, 53, 102, 1.6))
    surface_distance = math.acos(sum(a * b for a, b in zip(mumbai.position_km, new_york.position_km)) / EARTH_RADIUS_KM**2) * EARTH_RADIUS_KM
    assert visible(mumbai, sat_mumbai, 0)
    assert surface_distance > 10_000
    assert not (visible(mumbai, sat_mumbai, 0) and visible(sat_mumbai, new_york, 0))
    assert not (visible(mumbai, sat_singapore, 0) and visible(sat_singapore, new_york, 0))


def test_orbital_session_plans_through_bundle_ttl_before_choosing_first_hop():
    from leo_dtn.api_models import BundleInput, NodeInput, SimulationConfigurationInput
    from leo_dtn.service import SimulationSession

    orbits = ((59, 22), (102, 1.6), (0, 53), (45, 0), (90, 37), (135, 90), (180, 143), (225, 196))
    nodes = (
        NodeInput(
            node_id="GS-MUMBAI", kind="ground_station", buffer_capacity_bytes=10_000_000_000,
            position_km=ground_position(19.076, 72.878),
        ),
        *(NodeInput(
            node_id=f"SAT-{index:02d}", kind="satellite", buffer_capacity_bytes=10_000_000_000,
            orbit=CircularOrbit(550, 53, raan, phase),
        ) for index, (raan, phase) in enumerate(orbits, 1)),
        NodeInput(
            node_id="GS-NEW-YORK", kind="ground_station", buffer_capacity_bytes=10_000_000_000,
            position_km=ground_position(40.7128, -74.006),
        ),
    )
    ttl_us = 21_600_000_000
    config = SimulationConfigurationInput(
        nodes=nodes,
        bundles=(BundleInput(
            bundle_id="BND-001", source="GS-MUMBAI", destination="GS-NEW-YORK",
            payload_bytes=50_000_000, creation_time_us=2_000_000, ttl_us=ttl_us,
        ),),
        orbital_contact_generation=True,
        contact_sample_interval_us=10_000_000,
        minimum_elevation_deg=10,
        orbital_link_rate_bits_per_second=100_000_000,
    )
    session = SimulationSession(
        "sim-route-lookahead", config, 42, 600_000_000,
        "contact_aware_earliest_arrival",
    )
    session.initialize_bundles()

    assert session.horizon_us >= 2_000_000 + ttl_us
    snapshot = session.engine.run_until(2_000_000)
    first_hop = next(event for event in snapshot.events if event.kind == "transmission_started")
    first_contact = next(contact for contact in snapshot.contacts if contact.contact_id == first_hop.contact_id)
    assert (first_contact.from_node, first_contact.to_node) == ("GS-MUMBAI", "SAT-01")

    session._ensure_contact_plan(1_000_000_000)
    assert session.horizon_us >= 1_000_000_000 + ttl_us


def test_orbital_session_extends_plan_without_ending_at_initial_horizon():
    from leo_dtn.api_models import NodeInput, SimulationConfigurationInput
    from leo_dtn.service import SimulationSession

    config = SimulationConfigurationInput(
        nodes=(
            NodeInput(node_id="GS", kind="ground_station", buffer_capacity_bytes=1000, position_km=(6371, 0, 0)),
            NodeInput(node_id="SAT", kind="satellite", buffer_capacity_bytes=1000, orbit=CircularOrbit(500, 0, 0, 0)),
        ),
        orbital_contact_generation=True,
        contact_sample_interval_us=1_000_000,
    )
    initial_horizon = 5_000_000
    session = SimulationSession("sim-test", config, 8, initial_horizon, "contact_aware_earliest_arrival")
    first_window = session.engine.snapshot().contacts[0]
    initial_satellite_position = next(node.position_km for node in session.engine.snapshot().nodes if node.node.node_id == "SAT")
    session.start()
    _, reached_target = session.advance(target_time_us=initial_horizon, max_events=10_000)
    extended_window = next(contact for contact in session.engine.snapshot().contacts if contact.contact_id == first_window.contact_id)

    assert reached_target
    assert session.status == "running"
    assert session.horizon_us > initial_horizon
    assert extended_window.end_us > first_window.end_us
    assert next(node.position_km for node in session.engine.snapshot().nodes if node.node.node_id == "SAT") != initial_satellite_position

    session.reset()
    assert session.horizon_us == initial_horizon
    assert session.status == "ready"


def test_geometry_generated_contacts_can_deliver_a_real_bundle():
    from leo_dtn.engine import SimulationEngine

    mumbai = Node("GS-MUMBAI", NodeKind.GROUND_STATION, 100_000_000, ground_position(19.076, 72.878))
    singapore = Node("GS-SINGAPORE", NodeKind.GROUND_STATION, 100_000_000, ground_position(1.352, 103.820))
    sat_mumbai = Node("SAT-M", NodeKind.SATELLITE, 100_000_000, orbit=CircularOrbit(550, 53, 59, 22))
    sat_singapore = Node("SAT-S", NodeKind.SATELLITE, 100_000_000, orbit=CircularOrbit(550, 53, 102, 1.6))
    nodes = (mumbai, singapore, sat_mumbai, sat_singapore)
    contacts = generate_contact_plan(nodes, horizon_us=120_000_000, sample_interval_us=1_000_000)
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    engine.add_bundle(BundleRequest("B-DEMO", "GS-MUMBAI", "GS-SINGAPORE", 50_000_000, 2_000_000, 3_600_000_000))
    result = engine.run_until(120_000_000)
    bundle = next(item for item in result.bundles if item.bundle_id == "B-DEMO")
    assert bundle.status.value == "delivered"
    assert len(bundle.forwarding_history) >= 2
    assert all(item.from_position_km is not None and item.to_position_km is not None for item in bundle.forwarding_history)
