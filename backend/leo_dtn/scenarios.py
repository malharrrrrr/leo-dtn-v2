"""Deterministic network scenarios and selectable simulation presets."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .engine import SimulationEngine
from .model import BundleRequest, CircularOrbit, Contact, Node, NodeKind

SECOND = 1_000_000


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    scenario_id: str
    name: str
    description: str
    focus: str
    nodes: tuple[Node, ...]
    contacts: tuple[Contact, ...]
    bundles: tuple[BundleRequest, ...]
    orbital_contact_generation: bool = False
    contact_sample_interval_us: int = 10 * SECOND
    minimum_elevation_deg: float = 10.0
    orbital_link_rate_bits_per_second: int = 100_000_000
    bundle_generation_interval_us: int | None = None


def relay_vertical_slice_inputs() -> tuple[tuple[Node, ...], tuple[Contact, ...], tuple[BundleRequest, ...]]:
    """Return normalized inputs for the hand-checkable relay scenario."""
    nodes = (
        Node("GS-A", NodeKind.GROUND_STATION, 10_000),
        Node("SAT-R", NodeKind.SATELLITE, 10_000),
        Node("GS-B", NodeKind.GROUND_STATION, 10_000),
    )
    contacts = (
        Contact("C-A-R", "GS-A", "SAT-R", 0, 10 * SECOND, 8_000),
        Contact("C-R-B", "SAT-R", "GS-B", 20 * SECOND, 30 * SECOND, 8_000),
    )
    bundles = (
        BundleRequest(
            bundle_id="B1",
            source="GS-A",
            destination="GS-B",
            payload_bytes=1_000,
            creation_time_us=2 * SECOND,
            ttl_us=100 * SECOND,
        ),
    )
    return nodes, contacts, bundles


def relay_vertical_slice() -> SimulationEngine:
    """Ground station -> relay satellite -> ground station, with a carry gap."""
    nodes, contacts, bundles = relay_vertical_slice_inputs()
    engine = SimulationEngine(nodes=nodes, contacts=contacts)
    for bundle in bundles:
        engine.add_bundle(bundle)
    return engine


def scenario_catalog() -> tuple[ScenarioDefinition, ...]:
    """Return presets derived from the same moving Mumbai–New York LEO demo."""
    earth_radius = 6_371.0

    def earth_fixed_position(latitude_deg: float, longitude_deg: float) -> tuple[float, float, float]:
        latitude = math.radians(latitude_deg)
        longitude = math.radians(longitude_deg)
        return (
            earth_radius * math.cos(latitude) * math.cos(longitude),
            earth_radius * math.cos(latitude) * math.sin(longitude),
            earth_radius * math.sin(latitude),
        )

    default_orbits = ((59, 22), (102, 1.6), (0, 53), (45, 0), (90, 37), (135, 90), (180, 143), (225, 196))
    expanded_orbits = default_orbits + tuple(
        (22.5 + index * 45, 18 + index * 41)
        for index in range(8)
    )

    def leo_preset(
        *,
        scenario_id: str,
        name: str,
        description: str,
        focus: str,
        orbit_elements: tuple[tuple[float, float], ...],
        satellite_buffer_bytes: int = 10_000_000_000,
        ground_buffer_bytes: int = 10_000_000_000,
        bundle_payload_bytes: int = 50_000_000,
        bundle_interval_us: int = 60 * SECOND,
    ) -> ScenarioDefinition:
        nodes = (
            Node("GS-MUMBAI", NodeKind.GROUND_STATION, ground_buffer_bytes, earth_fixed_position(19.076, 72.878)),
            *(Node(
                f"SAT-{index:02d}", NodeKind.SATELLITE, satellite_buffer_bytes,
                orbit=CircularOrbit(550, 53, raan, phase),
            ) for index, (raan, phase) in enumerate(orbit_elements, 1)),
            Node("GS-NEW-YORK", NodeKind.GROUND_STATION, ground_buffer_bytes, earth_fixed_position(40.7128, -74.006)),
        )
        return ScenarioDefinition(
            scenario_id=scenario_id,
            name=name,
            description=description,
            focus=focus,
            nodes=nodes,
            contacts=(),
            bundles=(BundleRequest(
                "BND-001", "GS-MUMBAI", "GS-NEW-YORK", bundle_payload_bytes,
                2 * SECOND, 6 * 60 * 60 * SECOND,
            ),),
            orbital_contact_generation=True,
            bundle_generation_interval_us=bundle_interval_us,
        )

    return (
        leo_preset(
            scenario_id="leo-mumbai-new-york",
            name="Mumbai–New York · baseline",
            description="The same eight-satellite constellation and recurring traffic used by the default Simulation setup.",
            focus="Baseline moving LEO contacts and store-carry-forward delivery",
            orbit_elements=default_orbits,
        ),
        leo_preset(
            scenario_id="leo-sparse-constellation",
            name="Mumbai–New York · sparse constellation",
            description="Keeps the same stations, orbits, bundle, and traffic, but uses four of the baseline satellites.",
            focus="How fewer satellites affect contact availability and delivery",
            orbit_elements=default_orbits[::2],
        ),
        leo_preset(
            scenario_id="leo-limited-buffers",
            name="Mumbai–New York · limited buffers",
            description="Keeps the baseline constellation and traffic while reducing relay buffers to one bundle each.",
            focus="How finite satellite storage affects recurring bundle delivery",
            orbit_elements=default_orbits,
            satellite_buffer_bytes=50_000_000,
        ),
        leo_preset(
            scenario_id="leo-high-traffic",
            name="Mumbai–New York · high traffic",
            description="Keeps the baseline constellation but generates 100 MB bundles every 15 simulated seconds.",
            focus="How higher offered load affects delivery and queueing",
            orbit_elements=default_orbits,
            bundle_payload_bytes=100_000_000,
            bundle_interval_us=15 * SECOND,
        ),
        leo_preset(
            scenario_id="leo-expanded-constellation",
            name="Mumbai–New York · expanded constellation",
            description="Adds eight moving satellites to the same baseline orbital setup and traffic pattern.",
            focus="How a larger constellation changes generated contact opportunities",
            orbit_elements=expanded_orbits,
        ),
    )


def scenario_definition(scenario_id: str) -> ScenarioDefinition | None:
    """Look up a selectable preset or the retained hand-checkable relay fixture."""
    selected = next((item for item in scenario_catalog() if item.scenario_id == scenario_id), None)
    if selected is not None:
        return selected
    if scenario_id != "relay-vertical-slice":
        return None
    nodes, contacts, bundles = relay_vertical_slice_inputs()
    return ScenarioDefinition(
        scenario_id="relay-vertical-slice",
        name="Store-and-forward engine fixture",
        description="A small deterministic fixture for testing relay storage and contact-window event ordering.",
        focus="Engine verification; not a moving LEO preset",
        nodes=nodes,
        contacts=contacts,
        bundles=bundles,
    )
