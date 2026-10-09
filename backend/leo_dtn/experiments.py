"""Reproducible experiment runs and deterministic JSON/CSV exports."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any

from .engine import SimulationEngine
from .metrics import MetricReport, calculate_metrics
from .model import BundleRequest, Contact, ContactInterruption, Node, SimulationSnapshot
from .routing import ContactAwareEarliestArrival, RoutingPolicy

ENGINE_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class RunManifest:
    schema_version: int
    engine_version: str
    scenario_id: str
    random_seed: int
    routing_policy: str
    horizon_us: int
    run_status: str
    normalized_configuration_json: str


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    manifest: RunManifest
    snapshot: SimulationSnapshot
    metrics: MetricReport


def run_experiment(
    *,
    scenario_id: str,
    random_seed: int,
    horizon_us: int,
    nodes: tuple[Node, ...],
    contacts: tuple[Contact, ...],
    bundles: tuple[BundleRequest, ...],
    interruptions: tuple[ContactInterruption, ...] = (),
    routing_policy: RoutingPolicy | None = None,
) -> ExperimentResult:
    """Run the current contact-aware engine with a fully recorded configuration."""
    if not scenario_id.strip():
        raise ValueError("scenario ID must be non-empty")
    if not isinstance(random_seed, int) or isinstance(random_seed, bool):
        raise ValueError("random seed must be an integer")
    if not isinstance(horizon_us, int) or isinstance(horizon_us, bool) or horizon_us < 0:
        raise ValueError("horizon must be a nonnegative integer number of microseconds")

    normalized_nodes = tuple(sorted(nodes, key=lambda item: item.node_id))
    normalized_contacts = tuple(
        sorted(contacts, key=lambda item: (item.start_us, item.from_node, item.to_node, item.contact_id))
    )
    normalized_bundles = tuple(sorted(bundles, key=lambda item: (item.creation_time_us, item.bundle_id)))
    normalized_interruptions = tuple(
        sorted(interruptions, key=lambda item: (item.time_us, item.contact_id))
    )
    selected_routing_policy = (
        routing_policy if routing_policy is not None else ContactAwareEarliestArrival()
    )
    config = {
        "nodes": [_jsonable(node) for node in normalized_nodes],
        "contacts": [_jsonable(contact) for contact in normalized_contacts],
        "bundles": [_jsonable(bundle) for bundle in normalized_bundles],
        "interruptions": [_jsonable(interruption) for interruption in normalized_interruptions],
        "horizon_us": horizon_us,
        "routing_policy": selected_routing_policy.name,
        "random_seed": random_seed,
    }
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))

    engine = SimulationEngine(
        nodes=normalized_nodes,
        contacts=normalized_contacts,
        interruptions=normalized_interruptions,
        routing_policy=selected_routing_policy,
    )
    for bundle in normalized_bundles:
        engine.add_bundle(bundle)
    snapshot = engine.run_until(horizon_us)
    metrics = calculate_metrics(snapshot, horizon_us=horizon_us)
    manifest = RunManifest(
        schema_version=1,
        engine_version=ENGINE_VERSION,
        scenario_id=scenario_id,
        random_seed=random_seed,
        routing_policy=snapshot.routing_policy,
        horizon_us=horizon_us,
        run_status="completed_to_horizon",
        normalized_configuration_json=config_json,
    )
    return ExperimentResult(manifest=manifest, snapshot=snapshot, metrics=metrics)


def export_run_json(result: ExperimentResult) -> str:
    """Export manifest/config, immutable snapshot/event history, and metrics."""
    payload = {
        "manifest": {
            "schema_version": result.manifest.schema_version,
            "engine_version": result.manifest.engine_version,
            "scenario_id": result.manifest.scenario_id,
            "random_seed": result.manifest.random_seed,
            "routing_policy": result.manifest.routing_policy,
            "horizon_us": result.manifest.horizon_us,
            "run_status": result.manifest.run_status,
            "normalized_configuration": json.loads(
                result.manifest.normalized_configuration_json
            ),
        },
        "snapshot": _jsonable(result.snapshot),
        "metrics": _jsonable(result.metrics),
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def export_events_csv(result: ExperimentResult) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (*_csv_run_metadata_header(), "sequence", "time_us", "kind", "bundle_id", "node_id", "contact_id", "details_json")
    )
    for event in result.snapshot.events:
        writer.writerow(
            (
                *_csv_run_metadata_values(result.manifest),
                event.sequence,
                event.time_us,
                event.kind,
                event.bundle_id or "",
                event.node_id or "",
                event.contact_id or "",
                json.dumps(dict(event.details), sort_keys=True, separators=(",", ":")),
            )
        )
    return output.getvalue()


def export_scenario_csv(result: ExperimentResult) -> str:
    """Export the normalized node, contact, and bundle inputs as CSV rows."""
    configuration = json.loads(result.manifest.normalized_configuration_json)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            *_csv_run_metadata_header(),
            "record_type",
            "id",
            "node_kind",
            "from_node",
            "to_node",
            "buffer_capacity_bytes",
            "position_x_km",
            "position_y_km",
            "position_z_km",
            "start_us",
            "end_us",
            "rate_bits_per_second",
            "propagation_delay_us",
            "source",
            "destination",
            "payload_bytes",
            "creation_time_us",
            "ttl_us",
            "interruption_time_us",
        )
    )
    for node in configuration["nodes"]:
        position = node["position_km"] or ("", "", "")
        writer.writerow(
            (
                *_csv_run_metadata_values(result.manifest),
                "node",
                node["node_id"],
                node["kind"],
                "",
                "",
                node["buffer_capacity_bytes"],
                *position,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            )
        )
    for contact in configuration["contacts"]:
        writer.writerow((*_csv_run_metadata_values(result.manifest), "contact", contact["contact_id"], "", contact["from_node"], contact["to_node"], "", "", "", "", contact["start_us"], contact["end_us"], contact["rate_bits_per_second"], contact["propagation_delay_us"], "", "", "", "", "", ""))
    for bundle in configuration["bundles"]:
        writer.writerow((*_csv_run_metadata_values(result.manifest), "bundle", bundle["bundle_id"], "", "", "", "", "", "", "", "", "", "", "", bundle["source"], bundle["destination"], bundle["payload_bytes"], bundle["creation_time_us"], bundle["ttl_us"], ""))
    for interruption in configuration["interruptions"]:
        writer.writerow((*_csv_run_metadata_values(result.manifest), "interruption", interruption["contact_id"], "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", interruption["time_us"]))
    return output.getvalue()


def export_metrics_csv(result: ExperimentResult) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow((*_csv_run_metadata_header(), "metric", "scope", "value", "unit", "numerator", "denominator"))
    metrics = result.metrics
    for name, value, unit, numerator, denominator in (
        ("generated_count", metrics.generated_count, "bundles", "generation attempts", "run horizon"),
        ("delivered_count", metrics.delivered_count, "bundles", "delivered by cutoff", "run horizon"),
        ("undelivered_count", metrics.undelivered_count, "bundles", "generated minus delivered", "run horizon"),
        ("source_rejected_count", metrics.source_rejected_count, "bundles", "source admission failures", "generation attempts"),
        ("expired_count", metrics.expired_count, "bundles", "TTL expiration events", "generation attempts"),
        ("delivery_ratio", metrics.delivery_ratio, "fraction", metrics.delivered_count, metrics.generated_count),
        ("expiration_ratio", metrics.expiration_ratio, "fraction", metrics.expired_count, metrics.generated_count),
        ("mean_delivery_latency", metrics.mean_delivery_latency_us, "us", "delivered latency sum", metrics.delivered_count),
        ("median_delivery_latency", metrics.median_delivery_latency_us, "us", "delivered bundles", metrics.delivered_count),
        ("mean_hop_count", metrics.mean_hop_count, "hops", "delivered hop sum", metrics.delivered_count),
        ("mean_total_buffer_occupancy", metrics.mean_total_buffer_occupancy_bytes, "bytes", "occupancy byte-time integral", metrics.horizon_us),
        ("peak_total_buffer_occupancy", metrics.peak_total_buffer_occupancy_bytes, "bytes", "peak", "run horizon"),
        ("contact_utilization", metrics.contact_utilization_fraction, "fraction", "transmitted payload bits", "scheduled contact capacity bits"),
    ):
        writer.writerow((*_csv_run_metadata_values(result.manifest), name, "network", "" if value is None else value, unit, numerator, denominator))
    for node in metrics.per_node_buffer:
        writer.writerow((*_csv_run_metadata_values(result.manifest), "peak_buffer_occupancy", node.node_id, node.peak_occupancy_bytes, "bytes", "peak", "run horizon"))
        writer.writerow((*_csv_run_metadata_values(result.manifest), "mean_buffer_occupancy", node.node_id, node.mean_occupancy_bytes, "bytes", "occupancy byte-time integral", metrics.horizon_us))
    for contact in metrics.per_contact_utilization:
        writer.writerow((*_csv_run_metadata_values(result.manifest), "contact_utilization", contact.contact_id, "" if contact.utilization_fraction is None else contact.utilization_fraction, "fraction", contact.transmitted_payload_bits, contact.scheduled_capacity_bits))
    return output.getvalue()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _csv_run_metadata_header() -> tuple[str, ...]:
    return ("scenario_id", "random_seed", "routing_policy", "horizon_us", "run_status")


def _csv_run_metadata_values(manifest: RunManifest) -> tuple[str | int, ...]:
    return (
        manifest.scenario_id,
        manifest.random_seed,
        manifest.routing_policy,
        manifest.horizon_us,
        manifest.run_status,
    )
