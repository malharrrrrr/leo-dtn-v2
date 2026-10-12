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
    """Return the built-in, reproducible presets shown in the Scenarios tab."""
    relay_nodes, relay_contacts, relay_bundles = relay_vertical_slice_inputs()
    direct = ScenarioDefinition(
        scenario_id="direct-contact-baseline",
        name="Direct contact baseline",
        description="A single scheduled ground-station contact delivers one bundle without a relay.",
        focus="Direct delivery and serialization timing",
        nodes=(
            Node("GS-SOURCE", NodeKind.GROUND_STATION, 100_000_000),
            Node("GS-DEST", NodeKind.GROUND_STATION, 100_000_000),
        ),
        contacts=(Contact("C-DIRECT", "GS-SOURCE", "GS-DEST", 0, 20 * SECOND, 100_000_000),),
        bundles=(BundleRequest("BND-DIRECT", "GS-SOURCE", "GS-DEST", 1_000_000, 2 * SECOND, 60 * SECOND),),
    )
    relay = ScenarioDefinition(
        scenario_id="relay-vertical-slice",
        name="Store-and-forward relay",
        description="A bundle reaches a relay, waits through a contact gap, then forwards to its destination.",
        focus="Store-carry-forward behavior",
        nodes=relay_nodes,
        contacts=relay_contacts,
        bundles=relay_bundles,
    )
    multi_hop = ScenarioDefinition(
        scenario_id="intermittent-multi-hop",
        name="Intermittent multi-hop path",
        description="Three separated contact windows require two relays and observable waiting at each hop.",
        focus="Sequential contacts and multi-hop forwarding",
        nodes=(
            Node("GS-A", NodeKind.GROUND_STATION, 10_000),
            Node("SAT-R1", NodeKind.SATELLITE, 10_000),
            Node("SAT-R2", NodeKind.SATELLITE, 10_000),
            Node("GS-B", NodeKind.GROUND_STATION, 10_000),
        ),
        contacts=(
            Contact("C-A-R1", "GS-A", "SAT-R1", 0, 10 * SECOND, 8_000),
            Contact("C-R1-R2", "SAT-R1", "SAT-R2", 20 * SECOND, 30 * SECOND, 8_000),
            Contact("C-R2-B", "SAT-R2", "GS-B", 40 * SECOND, 50 * SECOND, 8_000),
        ),
        bundles=(BundleRequest("BND-MULTI", "GS-A", "GS-B", 1_000, 2 * SECOND, 100 * SECOND),),
    )
    buffer_pressure = ScenarioDefinition(
        scenario_id="relay-buffer-pressure",
        name="Relay buffer pressure",
        description="Two bundles are generated together while the source can store only one of them.",
        focus="Finite source storage and rejection",
        nodes=(
            Node("GS-A", NodeKind.GROUND_STATION, 1_000),
            Node("SAT-R", NodeKind.SATELLITE, 1_000),
            Node("GS-B", NodeKind.GROUND_STATION, 10_000),
        ),
        contacts=(
            Contact("C-A-R-1", "GS-A", "SAT-R", 0, 10 * SECOND, 8_000),
            Contact("C-R-B", "SAT-R", "GS-B", 10 * SECOND, 20 * SECOND, 8_000),
        ),
        bundles=(
            BundleRequest("BND-PRESS-1", "GS-A", "GS-B", 1_000, SECOND, 100 * SECOND),
            BundleRequest("BND-PRESS-2", "GS-A", "GS-B", 1_000, SECOND, 100 * SECOND),
        ),
    )
    earth_radius = 6_371.0

    def earth_fixed_position(latitude_deg: float, longitude_deg: float) -> tuple[float, float, float]:
        latitude = math.radians(latitude_deg)
        longitude = math.radians(longitude_deg)
        return (
            earth_radius * math.cos(latitude) * math.cos(longitude),
            earth_radius * math.cos(latitude) * math.sin(longitude),
            earth_radius * math.sin(latitude),
        )

    orbital_pairs = ((59, 22), (102, 1.6), (0, 53), (45, 0), (90, 37), (135, 90), (180, 143), (225, 196))
    orbital = ScenarioDefinition(
        scenario_id="leo-mumbai-new-york",
        name="Moving LEO constellation",
        description="A bundle travels between distant ground stations using moving satellites and geometry-derived contact windows.",
        focus="Orbital motion and changing line-of-sight contacts",
        nodes=(
            Node("GS-MUMBAI", NodeKind.GROUND_STATION, 10_000_000_000, earth_fixed_position(19.076, 72.878)),
            *(Node(
                f"SAT-{index:02d}", NodeKind.SATELLITE, 10_000_000_000,
                orbit=CircularOrbit(550, 53, raan, phase),
            ) for index, (raan, phase) in enumerate(orbital_pairs, 1)),
            Node("GS-NEW-YORK", NodeKind.GROUND_STATION, 10_000_000_000, earth_fixed_position(40.7128, -74.006)),
        ),
        contacts=(),
        bundles=(BundleRequest("BND-LEO", "GS-MUMBAI", "GS-NEW-YORK", 50_000_000, 2 * SECOND, 6 * 60 * 60 * SECOND),),
        orbital_contact_generation=True,
    )
    return direct, relay, multi_hop, buffer_pressure, orbital
