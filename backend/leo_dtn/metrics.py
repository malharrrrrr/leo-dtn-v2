"""Pure metric calculations over an immutable simulation snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median

from .model import BundleStatus, SimulationSnapshot


@dataclass(frozen=True, slots=True)
class NodeBufferMetrics:
    node_id: str
    peak_occupancy_bytes: int
    mean_occupancy_bytes: float
    mean_capacity_fraction: float | None


@dataclass(frozen=True, slots=True)
class ContactUtilizationMetrics:
    contact_id: str
    transmitted_payload_bits: int
    scheduled_capacity_bits: float
    utilization_fraction: float | None


@dataclass(frozen=True, slots=True)
class MetricReport:
    horizon_us: int
    generated_count: int
    delivered_count: int
    undelivered_count: int
    source_rejected_count: int
    expired_count: int
    delivery_ratio: float | None
    expiration_ratio: float | None
    mean_delivery_latency_us: float | None
    median_delivery_latency_us: float | None
    mean_hop_count: float | None
    median_hop_count: float | None
    mean_total_buffer_occupancy_bytes: float
    peak_total_buffer_occupancy_bytes: int
    mean_total_buffer_capacity_fraction: float | None
    contact_utilization_fraction: float | None
    status_counts: tuple[tuple[str, int], ...]
    per_node_buffer: tuple[NodeBufferMetrics, ...]
    per_contact_utilization: tuple[ContactUtilizationMetrics, ...]


def calculate_metrics(snapshot: SimulationSnapshot, *, horizon_us: int) -> MetricReport:
    """Calculate run-cutoff metrics; pending bundles remain undelivered, not expired."""
    if not isinstance(horizon_us, int) or isinstance(horizon_us, bool) or horizon_us < 0:
        raise ValueError("metric horizon must be a nonnegative integer number of microseconds")
    if horizon_us != snapshot.time_us:
        raise ValueError("metric horizon must match the snapshot's simulated time")

    bundles = {bundle.bundle_id: bundle for bundle in snapshot.bundles}
    generated_ids = {
        event.bundle_id
        for event in snapshot.events
        if event.kind == "bundle_generated" and event.bundle_id is not None and event.time_us <= horizon_us
    }
    delivered_times: dict[str, int] = {}
    serialized_counts: dict[str, int] = {}
    for event in snapshot.events:
        if event.time_us > horizon_us or event.bundle_id is None:
            continue
        if event.kind == "bundle_delivered":
            delivered_times[event.bundle_id] = event.time_us
        elif event.kind == "transmission_completed" and event.contact_id is not None:
            serialized_counts[event.contact_id] = serialized_counts.get(event.contact_id, 0) + bundles[
                event.bundle_id
            ].payload_bytes * 8

    delivered_ids = set(delivered_times) & generated_ids
    generated_count = len(generated_ids)
    delivered_count = len(delivered_ids)
    expired_count = sum(
        1
        for bundle_id in generated_ids
        if bundle_id in bundles and bundles[bundle_id].status == BundleStatus.EXPIRED
    )
    rejected_count = sum(
        1
        for bundle_id in generated_ids
        if bundle_id in bundles and bundles[bundle_id].status == BundleStatus.REJECTED_AT_SOURCE
    )
    latencies = [
        delivered_times[bundle_id] - bundles[bundle_id].creation_time_us
        for bundle_id in delivered_ids
    ]
    hops = [len(bundles[bundle_id].forwarding_history) for bundle_id in delivered_ids]

    occupancy_integrals: dict[str, int] = {}
    samples_by_node: dict[str, list[tuple[int, int]]] = {
        node.node.node_id: [(0, 0)] for node in snapshot.nodes
    }
    for sample in snapshot.buffer_samples:
        if sample.time_us <= horizon_us:
            samples_by_node.setdefault(sample.node_id, []).append(
                (sample.time_us, sample.occupancy_bytes)
            )

    per_node: list[NodeBufferMetrics] = []
    for node_snapshot in snapshot.nodes:
        node_id = node_snapshot.node.node_id
        samples = sorted(samples_by_node.get(node_id, [(0, 0)]), key=lambda item: item[0])
        occupancy = 0
        last_time = 0
        integral = 0
        peak = 0
        for sample_time, sample_occupancy in samples:
            if sample_time > horizon_us:
                break
            integral += occupancy * (sample_time - last_time)
            occupancy = sample_occupancy
            peak = max(peak, occupancy)
            last_time = sample_time
        integral += occupancy * (horizon_us - last_time)
        occupancy_integrals[node_id] = integral
        average = integral / horizon_us if horizon_us else 0.0
        capacity = node_snapshot.node.buffer_capacity_bytes
        per_node.append(
            NodeBufferMetrics(
                node_id=node_id,
                peak_occupancy_bytes=peak,
                mean_occupancy_bytes=average,
                mean_capacity_fraction=(average / capacity if capacity else None),
            )
        )

    total_capacity = sum(node.node.buffer_capacity_bytes for node in snapshot.nodes)
    total_integral = sum(occupancy_integrals.values())
    total_mean = total_integral / horizon_us if horizon_us else 0.0
    current_occupancy = {node.node.node_id: 0 for node in snapshot.nodes}
    peak_total = 0
    samples_by_time: dict[int, dict[str, int]] = {}
    for sample in snapshot.buffer_samples:
        if sample.time_us <= horizon_us:
            samples_by_time.setdefault(sample.time_us, {})[sample.node_id] = sample.occupancy_bytes
    for sample_time in sorted(samples_by_time):
        current_occupancy.update(samples_by_time[sample_time])
        peak_total = max(peak_total, sum(current_occupancy.values()))

    per_contact: list[ContactUtilizationMetrics] = []
    for contact in snapshot.contacts:
        measured_us = max(0, min(contact.end_us, horizon_us) - max(contact.start_us, 0))
        capacity_bits = contact.rate_bits_per_second * measured_us / 1_000_000
        sent_bits = serialized_counts.get(contact.contact_id, 0)
        per_contact.append(
            ContactUtilizationMetrics(
                contact_id=contact.contact_id,
                transmitted_payload_bits=sent_bits,
                scheduled_capacity_bits=capacity_bits,
                utilization_fraction=(sent_bits / capacity_bits if capacity_bits else None),
            )
        )
    total_contact_capacity = sum(item.scheduled_capacity_bits for item in per_contact)
    total_sent_bits = sum(item.transmitted_payload_bits for item in per_contact)
    status_counts = tuple(
        (status.value, sum(1 for bundle_id in generated_ids if bundles[bundle_id].status == status))
        for status in BundleStatus
    )

    return MetricReport(
        horizon_us=horizon_us,
        generated_count=generated_count,
        delivered_count=delivered_count,
        undelivered_count=generated_count - delivered_count,
        source_rejected_count=rejected_count,
        expired_count=expired_count,
        delivery_ratio=(delivered_count / generated_count if generated_count else None),
        expiration_ratio=(expired_count / generated_count if generated_count else None),
        mean_delivery_latency_us=(mean(latencies) if latencies else None),
        median_delivery_latency_us=(median(latencies) if latencies else None),
        mean_hop_count=(mean(hops) if hops else None),
        median_hop_count=(median(hops) if hops else None),
        mean_total_buffer_occupancy_bytes=total_mean,
        peak_total_buffer_occupancy_bytes=peak_total,
        mean_total_buffer_capacity_fraction=(total_mean / total_capacity if total_capacity else None),
        contact_utilization_fraction=(
            total_sent_bits / total_contact_capacity if total_contact_capacity else None
        ),
        status_counts=status_counts,
        per_node_buffer=tuple(per_node),
        per_contact_utilization=tuple(per_contact),
    )
