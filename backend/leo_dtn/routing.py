"""Time-dependent earliest-arrival routing over a precomputed contact plan."""

from __future__ import annotations

import heapq
from collections.abc import Collection

from .model import Contact

MICROSECONDS_PER_SECOND = 1_000_000


def serialization_duration_us(payload_bytes: int, rate_bits_per_second: int) -> int:
    """Return the ceiling of payload serialization time in integer microseconds."""
    numerator = payload_bytes * 8 * MICROSECONDS_PER_SECOND
    return (numerator + rate_bits_per_second - 1) // rate_bits_per_second


def earliest_arrival_path(
    *,
    source: str,
    destination: str,
    start_time_us: int,
    payload_bytes: int,
    contacts: tuple[Contact, ...],
    forbidden_nodes: Collection[str] = (),
) -> tuple[Contact, ...] | None:
    """Find a feasible time-respecting path; ties follow contact IDs deterministically."""
    # Heap order is arrival time, then node and path IDs for reproducible ties.
    heap: list[tuple[int, str, tuple[str, ...], tuple[Contact, ...]]] = [
        (start_time_us, source, (), ())
    ]
    best_arrival: dict[str, int] = {source: start_time_us}
    by_id = {contact.contact_id: contact for contact in contacts}

    while heap:
        arrival_at_node, node_id, visited, path = heapq.heappop(heap)
        if arrival_at_node != best_arrival.get(node_id):
            continue
        if node_id == destination:
            return path

        for contact in sorted(contacts, key=lambda item: (item.start_us, item.contact_id)):
            if (
                contact.from_node != node_id
                or contact.to_node in visited
                or (contact.to_node in forbidden_nodes and contact.to_node != destination)
            ):
                continue
            tx_start = max(arrival_at_node, contact.start_us)
            duration = serialization_duration_us(
                payload_bytes, contact.rate_bits_per_second
            )
            # The full serialization interval must end strictly before contact end.
            if tx_start + duration >= contact.end_us:
                continue
            next_arrival = tx_start + duration + contact.propagation_delay_us
            previous = best_arrival.get(contact.to_node)
            if previous is not None and previous <= next_arrival:
                continue
            best_arrival[contact.to_node] = next_arrival
            next_visited = (*visited, node_id)
            next_path = (*path, by_id[contact.contact_id])
            heapq.heappush(
                heap,
                (next_arrival, contact.to_node, next_visited, next_path),
            )
    return None
