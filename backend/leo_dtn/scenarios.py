"""Hand-checkable deterministic scenarios for development and examples."""

from .engine import SimulationEngine
from .model import BundleRequest, Contact, Node, NodeKind

SECOND = 1_000_000


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
