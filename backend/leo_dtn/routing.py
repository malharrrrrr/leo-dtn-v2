"""Time-dependent earliest-arrival routing over a precomputed contact plan."""

from __future__ import annotations

import heapq
from collections.abc import Collection
from typing import Protocol

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
            # The last bit must arrive strictly before contact end.
            if tx_start + duration + contact.propagation_delay_us >= contact.end_us:
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


class RoutingPolicy(Protocol):
    """Replaceable path-selection interface; the engine still owns execution."""

    name: str

    def find_path(
        self,
        *,
        source: str,
        destination: str,
        start_time_us: int,
        payload_bytes: int,
        contacts: tuple[Contact, ...],
        forbidden_nodes: Collection[str],
    ) -> tuple[Contact, ...] | None: ...


class ContactAwareEarliestArrival:
    name = "contact_aware_earliest_arrival"

    def find_path(
        self,
        *,
        source: str,
        destination: str,
        start_time_us: int,
        payload_bytes: int,
        contacts: tuple[Contact, ...],
        forbidden_nodes: Collection[str],
    ) -> tuple[Contact, ...] | None:
        return earliest_arrival_path(
            source=source,
            destination=destination,
            start_time_us=start_time_us,
            payload_bytes=payload_bytes,
            contacts=contacts,
            forbidden_nodes=forbidden_nodes,
        )


class StaticMinimumHop:
    """Minimum-hop route over the contact union; it ignores temporal path quality."""

    name = "static_minimum_hop"

    def find_path(
        self,
        *,
        source: str,
        destination: str,
        start_time_us: int,
        payload_bytes: int,
        contacts: tuple[Contact, ...],
        forbidden_nodes: Collection[str],
    ) -> tuple[Contact, ...] | None:
        adjacency: dict[str, set[str]] = {}
        for contact in contacts:
            if contact.to_node not in forbidden_nodes or contact.to_node == destination:
                adjacency.setdefault(contact.from_node, set()).add(contact.to_node)

        queue: list[tuple[str, tuple[str, ...]]] = [(source, ())]
        visited = {source}
        first_hop: str | None = None
        while queue:
            node_id, path = queue.pop(0)
            if node_id == destination:
                if path:
                    first_hop = path[0]
                break
            for neighbor in sorted(adjacency.get(node_id, ())):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, (*path, neighbor)))
        if first_hop is None:
            return None

        feasible: list[tuple[int, str, Contact]] = []
        for contact in contacts:
            if contact.from_node != source or contact.to_node != first_hop:
                continue
            start = max(start_time_us, contact.start_us)
            duration = serialization_duration_us(payload_bytes, contact.rate_bits_per_second)
            if start + duration + contact.propagation_delay_us < contact.end_us:
                feasible.append((start, contact.contact_id, contact))
        if not feasible:
            return None
        return (min(feasible, key=lambda item: (item[0], item[1]))[2],)
