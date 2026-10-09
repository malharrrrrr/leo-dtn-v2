"""FastAPI adapter for controlling and inspecting in-memory simulations."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response

from .api_models import (
    AdvanceRequest,
    AdvanceResponse,
    ActiveTransmissionResponse,
    BundleResponse,
    ContactResponse,
    CreateSimulationRequest,
    EventResponse,
    MetricsResponse,
    NodeResponse,
    RunCreatedResponse,
    ScenarioResponse,
    ScenarioSummary,
    SimulationSnapshotResponse,
    SimulationStatusResponse,
)
from .experiments import (
    ENGINE_VERSION,
    ExperimentResult,
    RunManifest,
    export_events_csv,
    export_metrics_csv,
    export_run_json,
    export_scenario_csv,
)
from .metrics import calculate_metrics
from .service import InvalidRunTransition, SimulationManager, SimulationSession, default_scenario


def create_app(manager: SimulationManager | None = None) -> FastAPI:
    app = FastAPI(title="LEO-DTN Simulation API", version="0.1.0")
    app.state.simulations = manager or SimulationManager()

    def get_session(simulation_id: str) -> SimulationSession:
        try:
            return app.state.simulations.get(simulation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="simulation not found") from exc

    def translate_transition(action):
        try:
            return action()
        except InvalidRunTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/scenarios", response_model=tuple[ScenarioSummary, ...])
    def list_scenarios():
        return (
            ScenarioSummary(
                scenario_id="relay-vertical-slice",
                name="Relay vertical slice",
                description="A source, relay, and destination connected by time-dependent contacts.",
            ),
        )

    @app.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
    def inspect_scenario(scenario_id: str):
        try:
            config = default_scenario(scenario_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="scenario not found") from exc
        return ScenarioResponse(
            scenario_id=scenario_id,
            name="Relay vertical slice",
            description="A source, relay, and destination connected by time-dependent contacts.",
            configuration=config,
        )

    @app.post("/simulations", response_model=RunCreatedResponse, status_code=201)
    def create_simulation(request: CreateSimulationRequest):
        try:
            session = app.state.simulations.create(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="scenario not found") from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _status(session, RunCreatedResponse, normalized_configuration=session.configuration)

    @app.get("/simulations/{simulation_id}", response_model=SimulationStatusResponse)
    def inspect_simulation(simulation_id: str):
        return _status(get_session(simulation_id))

    @app.post("/simulations/{simulation_id}/start", response_model=SimulationSnapshotResponse)
    def start_simulation(simulation_id: str):
        session = get_session(simulation_id)
        translate_transition(session.start)
        return _snapshot(session)

    @app.post("/simulations/{simulation_id}/pause", response_model=SimulationSnapshotResponse)
    def pause_simulation(simulation_id: str):
        session = get_session(simulation_id)
        translate_transition(session.pause)
        return _snapshot(session)

    @app.post("/simulations/{simulation_id}/resume", response_model=SimulationSnapshotResponse)
    def resume_simulation(simulation_id: str):
        session = get_session(simulation_id)
        translate_transition(session.resume)
        return _snapshot(session)

    @app.post("/simulations/{simulation_id}/step", response_model=SimulationSnapshotResponse)
    def step_simulation(simulation_id: str):
        session = get_session(simulation_id)
        translate_transition(session.step)
        return _snapshot(session)

    @app.post("/simulations/{simulation_id}/advance", response_model=AdvanceResponse)
    def advance_simulation(simulation_id: str, request: AdvanceRequest):
        session = get_session(simulation_id)
        target = request.target_time_us if request.target_time_us is not None else session.horizon_us
        try:
            processed, reached = session.advance(target_time_us=target, max_events=request.max_events)
        except InvalidRunTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return AdvanceResponse(
            simulation=_snapshot(session), target_time_us=target,
            events_processed=processed, reached_target=reached,
        )

    @app.post("/simulations/{simulation_id}/reset", response_model=SimulationSnapshotResponse)
    def reset_simulation(simulation_id: str):
        session = get_session(simulation_id)
        session.reset()
        return _snapshot(session)

    @app.get("/simulations/{simulation_id}/nodes", response_model=tuple[NodeResponse, ...])
    def list_nodes(simulation_id: str):
        return _snapshot(get_session(simulation_id)).nodes

    @app.get("/simulations/{simulation_id}/nodes/{node_id}", response_model=NodeResponse)
    def get_node(simulation_id: str, node_id: str):
        nodes = _snapshot(get_session(simulation_id)).nodes
        for node in nodes:
            if node.node_id == node_id:
                return node
        raise HTTPException(status_code=404, detail="node not found")

    @app.get("/simulations/{simulation_id}/contacts", response_model=tuple[ContactResponse, ...])
    def list_contacts(simulation_id: str):
        return _snapshot(get_session(simulation_id)).contacts

    @app.get("/simulations/{simulation_id}/bundles", response_model=tuple[BundleResponse, ...])
    def list_bundles(simulation_id: str):
        return _snapshot(get_session(simulation_id)).bundles

    @app.get("/simulations/{simulation_id}/bundles/{bundle_id}", response_model=BundleResponse)
    def get_bundle(simulation_id: str, bundle_id: str):
        for bundle in _snapshot(get_session(simulation_id)).bundles:
            if bundle.bundle_id == bundle_id:
                return bundle
        raise HTTPException(status_code=404, detail="bundle not found")

    @app.get("/simulations/{simulation_id}/events", response_model=tuple[EventResponse, ...])
    def list_events(
        simulation_id: str,
        after_sequence: int = Query(default=-1, ge=-1),
        limit: int = Query(default=100, ge=1, le=1000),
    ):
        snapshot = _snapshot(get_session(simulation_id))
        return tuple(event for event in snapshot.events if event.sequence > after_sequence)[:limit]

    @app.get("/simulations/{simulation_id}/metrics", response_model=MetricsResponse)
    def get_metrics(simulation_id: str):
        session = get_session(simulation_id)
        with session.lock:
            current_time = session.engine.time_us
            snapshot = session.engine.snapshot()
        report = calculate_metrics(snapshot, horizon_us=current_time)
        return report

    @app.get("/simulations/{simulation_id}/export")
    def export_simulation(simulation_id: str, format: Literal["json", "scenario_csv", "events_csv", "metrics_csv"]):
        session = get_session(simulation_id)
        with session.lock:
            snapshot = session.engine.snapshot()
            configuration = session.configuration
            random_seed = session.random_seed
            routing_policy_name = session.routing_policy_name
            run_status = session.status
        horizon = snapshot.time_us
        metrics = calculate_metrics(snapshot, horizon_us=horizon)
        config_json = json.dumps(configuration.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        result = ExperimentResult(
            manifest=RunManifest(
                schema_version=1,
                engine_version=ENGINE_VERSION,
                scenario_id=(
                    "relay-vertical-slice"
                    if configuration == default_scenario("relay-vertical-slice")
                    else "inline"
                ),
                random_seed=random_seed,
                routing_policy=routing_policy_name,
                horizon_us=horizon,
                run_status=run_status,
                normalized_configuration_json=config_json,
            ),
            snapshot=snapshot,
            metrics=metrics,
        )
        if format == "json":
            body, media = export_run_json(result), "application/json"
        elif format == "scenario_csv":
            body, media = export_scenario_csv(result), "text/csv"
        elif format == "events_csv":
            body, media = export_events_csv(result), "text/csv"
        else:
            body, media = export_metrics_csv(result), "text/csv"
        return Response(
            content=body,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{simulation_id}-{format}.{"json" if format == "json" else "csv"}"'},
        )

    return app


def _status(session: SimulationSession, response_type=SimulationStatusResponse, **extra):
    with session.lock:
        return response_type(
            simulation_id=session.simulation_id,
            status=session.status,
            simulated_time_us=session.engine.time_us,
            horizon_us=session.horizon_us,
            random_seed=session.random_seed,
            routing_policy=session.routing_policy_name,
            node_count=len(session.configuration.nodes),
            contact_count=len(session.configuration.contacts),
            bundle_count=len(session.configuration.bundles),
            **extra,
        )


def _snapshot(session: SimulationSession) -> SimulationSnapshotResponse:
    with session.lock:
        return _snapshot_locked(session)


def _snapshot_locked(session: SimulationSession) -> SimulationSnapshotResponse:
    snapshot = session.engine.snapshot()
    time_us = snapshot.time_us
    interrupted = {
        event.contact_id
        for event in snapshot.events
        if event.kind == "contact_interrupted" and event.contact_id is not None
    }
    contacts = []
    for contact in snapshot.contacts:
        if contact.contact_id in interrupted:
            state = "interrupted"
        elif time_us < contact.start_us:
            state = "planned"
        elif time_us < contact.end_us:
            state = "active"
        else:
            state = "completed"
        contacts.append(ContactResponse(
            contact_id=contact.contact_id, from_node=contact.from_node, to_node=contact.to_node,
            start_us=contact.start_us, end_us=contact.end_us,
            rate_bits_per_second=contact.rate_bits_per_second,
            propagation_delay_us=contact.propagation_delay_us, status=state,
        ))
    return SimulationSnapshotResponse(
        simulation_id=session.simulation_id, status=session.status, time_us=time_us,
        horizon_us=session.horizon_us, routing_policy=snapshot.routing_policy,
        nodes=tuple(NodeResponse(
            node_id=item.node.node_id, kind=item.node.kind,
            buffer_capacity_bytes=item.node.buffer_capacity_bytes,
            buffer_occupancy_bytes=item.buffer_occupancy_bytes,
            position_km=item.node.position_km,
        ) for item in snapshot.nodes),
        contacts=tuple(contacts),
        bundles=tuple(BundleResponse(
            bundle_id=item.bundle_id, source=item.source, destination=item.destination,
            payload_bytes=item.payload_bytes, creation_time_us=item.creation_time_us,
            expiry_time_us=item.expiry_time_us, holder=item.holder, status=item.status,
            forwarding_history=tuple(record.__dict__ if hasattr(record, "__dict__") else {
                "from_node": record.from_node, "to_node": record.to_node,
                "contact_id": record.contact_id,
                "transmission_start_us": record.transmission_start_us,
                "serialization_complete_us": record.serialization_complete_us,
                "receiver_acceptance_us": record.receiver_acceptance_us,
            } for record in item.forwarding_history),
        ) for item in snapshot.bundles),
        active_transmissions=tuple(ActiveTransmissionResponse(
            bundle_id=item.bundle_id, contact_id=item.contact_id,
            from_node=item.from_node, to_node=item.to_node,
            start_time_us=item.start_time_us,
            serialization_complete_us=item.serialization_complete_us,
        ) for item in snapshot.active_transmissions),
        events=tuple(EventResponse(
            sequence=item.sequence, time_us=item.time_us, kind=item.kind,
            bundle_id=item.bundle_id, node_id=item.node_id, contact_id=item.contact_id,
            details=dict(item.details),
        ) for item in snapshot.events),
    )


app = create_app()
