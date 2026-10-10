import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


@pytest.fixture(scope="module")
def api_client():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "leo_dtn.api:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=Path(__file__).parents[1],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2.0)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("Uvicorn exited before becoming ready")
        try:
            if client.get("/scenarios").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        process.terminate()
        pytest.fail("Uvicorn did not become ready within 10 seconds")
    yield client
    client.close()
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def request(client: httpx.Client, method: str, path: str, *, json_body=None):
    return client.request(method, path, json=json_body)


def create_run(client: httpx.Client, *, horizon: int = 100_000) -> str:
    response = request(client, "POST", "/simulations", json_body={
        "scenario_id": "relay-vertical-slice", "random_seed": 19, "horizon_us": horizon,
    })
    assert response.status_code == 201, response.text
    return response.json()["simulation_id"]


def test_scenario_and_simulation_snapshot_are_read_only_projections(api_client):
    scenario = request(api_client, "GET", "/scenarios/relay-vertical-slice")
    assert scenario.status_code == 200
    assert len(scenario.json()["configuration"]["nodes"]) == 3

    simulation_id = create_run(api_client)
    snapshot = request(api_client, "GET", f"/simulations/{simulation_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["status"] == "ready"
    assert snapshot.json()["simulated_time_us"] == 0
    full_snapshot = request(api_client, "GET", f"/simulations/{simulation_id}/snapshot")
    assert len(full_snapshot.json()["nodes"]) == 3
    nodes = request(api_client, "GET", f"/simulations/{simulation_id}/nodes").json()
    assert {node["node_id"] for node in nodes} == {"GS-A", "SAT-R", "GS-B"}
    assert request(api_client, "GET", f"/simulations/{simulation_id}/nodes/missing").status_code == 404


def test_run_controls_advance_only_on_command_and_reset_to_initial_state(api_client):
    simulation_id = create_run(api_client)
    assert request(api_client, "POST", f"/simulations/{simulation_id}/pause").status_code == 409
    started = request(api_client, "POST", f"/simulations/{simulation_id}/start")
    assert started.status_code == 200
    assert started.json()["time_us"] == 0
    advanced = request(api_client, "POST", f"/simulations/{simulation_id}/advance", json_body={
        "target_time_us": 20_000, "max_events": 2,
    })
    assert advanced.status_code == 200
    assert 0 < advanced.json()["events_processed"] <= 2
    assert advanced.json()["simulation"]["time_us"] <= 20_000
    assert request(api_client, "POST", f"/simulations/{simulation_id}/pause").status_code == 200
    assert request(api_client, "POST", f"/simulations/{simulation_id}/resume").status_code == 200
    reset = request(api_client, "POST", f"/simulations/{simulation_id}/reset")
    assert reset.status_code == 200
    assert reset.json()["status"] == "ready"
    assert reset.json()["time_us"] == 0


def test_validation_not_found_events_metrics_and_exports(api_client):
    assert request(api_client, "GET", "/scenarios/nope").status_code == 404
    assert request(api_client, "GET", "/simulations/nope").status_code == 404
    assert request(api_client, "POST", "/simulations", json_body={
        "scenario_id": "nope", "random_seed": 1, "horizon_us": 100,
    }).status_code == 404
    assert request(api_client, "POST", "/simulations", json_body={
        "scenario_id": "x", "configuration": {"nodes": []}, "random_seed": 1, "horizon_us": 10,
    }).status_code == 422

    simulation_id = create_run(api_client, horizon=100_000_000)
    assert request(api_client, "POST", f"/simulations/{simulation_id}/start").status_code == 200
    assert request(api_client, "POST", f"/simulations/{simulation_id}/advance", json_body={
        "target_time_us": 100_000_000, "max_events": 10_000,
    }).status_code == 200
    events = request(api_client, "GET", f"/simulations/{simulation_id}/events?after_sequence=-1&limit=2")
    assert events.status_code == 200
    assert len(events.json()) <= 2
    assert request(api_client, "GET", f"/simulations/{simulation_id}/metrics").status_code == 200
    assert request(api_client, "GET", f"/simulations/{simulation_id}/bundles").status_code == 200

    for export_format, content_type in (
        ("json", "application/json"), ("scenario_csv", "text/csv"),
        ("events_csv", "text/csv"), ("metrics_csv", "text/csv"),
    ):
        response = request(api_client, "GET", f"/simulations/{simulation_id}/export?format={export_format}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(content_type)
        assert response.content


def test_advance_rejects_invalid_target_and_requires_running_state(api_client):
    simulation_id = create_run(api_client)
    assert request(api_client, "POST", f"/simulations/{simulation_id}/advance", json_body={
        "target_time_us": 10,
    }).status_code == 409
    assert request(api_client, "POST", f"/simulations/{simulation_id}/start").status_code == 200
    assert request(api_client, "POST", f"/simulations/{simulation_id}/advance", json_body={
        "target_time_us": 100_001,
    }).status_code == 422


def test_orbital_configuration_returns_engine_state_and_generated_contacts(api_client):
    created = request(api_client, "POST", "/simulations", json_body={
        "configuration": {
            "nodes": [
                {"node_id": "GS", "kind": "ground_station", "buffer_capacity_bytes": 1000, "position_km": [6371, 0, 0]},
                {"node_id": "SAT", "kind": "satellite", "buffer_capacity_bytes": 1000, "orbit": {
                    "altitude_km": 500, "inclination_deg": 0, "raan_deg": 0, "phase_deg": 0,
                }},
            ],
            "contacts": [], "bundles": [], "interruptions": [],
            "orbital_contact_generation": True,
            "contact_sample_interval_us": 1_000_000,
            "minimum_elevation_deg": 10,
            "orbital_link_rate_bits_per_second": 1_000_000,
        },
        "random_seed": 8,
        "horizon_us": 5_000_000,
    })
    assert created.status_code == 201, created.text
    simulation_id = created.json()["simulation_id"]
    snapshot = request(api_client, "GET", f"/simulations/{simulation_id}/snapshot").json()
    satellite = next(node for node in snapshot["nodes"] if node["node_id"] == "SAT")
    assert satellite["position_km"] is not None
    assert satellite["velocity_km_s"] is not None
    assert len(snapshot["contacts"]) == 2


def test_orbital_run_advances_without_dashboard_polling_and_pause_stops_it(api_client):
    created = request(api_client, "POST", "/simulations", json_body={
        "configuration": {
            "nodes": [
                {"node_id": "GS", "kind": "ground_station", "buffer_capacity_bytes": 1000, "position_km": [6371, 0, 0]},
                {"node_id": "SAT", "kind": "satellite", "buffer_capacity_bytes": 1000, "orbit": {
                    "altitude_km": 500, "inclination_deg": 0, "raan_deg": 0, "phase_deg": 0,
                }},
            ],
            "contacts": [], "bundles": [], "interruptions": [],
            "orbital_contact_generation": True,
            "contact_sample_interval_us": 1_000_000,
        },
        "random_seed": 1,
        "horizon_us": 5_000_000,
    })
    simulation_id = created.json()["simulation_id"]
    assert request(api_client, "POST", f"/simulations/{simulation_id}/start").status_code == 200
    time.sleep(0.35)
    advanced = request(api_client, "GET", f"/simulations/{simulation_id}/snapshot").json()
    assert advanced["time_us"] > 0

    paused = request(api_client, "POST", f"/simulations/{simulation_id}/pause").json()
    paused_time = paused["time_us"]
    time.sleep(0.25)
    after_wait = request(api_client, "GET", f"/simulations/{simulation_id}/snapshot").json()
    assert after_wait["time_us"] == paused_time
