# LEO-DTN

LEO-DTN is a local simulation and visualization project for studying Delay-Tolerant Networking in Low Earth Orbit satellite networks. Its deterministic Python engine models store-carry-forward bundles, finite buffers, expiration, routing, circular satellite motion, and contact windows generated from Earth line of sight; FastAPI exposes engine state to a Next.js dashboard for configuring and inspecting runs. The orbit model is a simplified academic approximation, not an operational ephemeris or full satellite link model.

## Run locally

You need Python, Node.js, npm, and `uv` for the initial Python environment setup. From the repository root, create the backend virtual environment and install the backend with its test dependencies (skip these two commands if `backend/.venv` is already set up):

```powershell
uv venv --seed --python 3.14 backend/.venv
uv pip install --python backend/.venv/Scripts/python.exe -e "backend[test]"
```

Open two terminals in the repository root. Start the API in the first:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn leo_dtn.api:app --app-dir backend --reload
```

Start the dashboard in the second:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The dashboard uses the API at `http://127.0.0.1:8000` by default. Orbital runs plan contacts through configured bundle TTL, then maintain that lookahead as simulated time advances so earliest-arrival routing can compare complete paths before forwarding. Runs generate a bundle every 60 simulated seconds by default. The API advances those runs while it remains on, even if the dashboard is closed; pausing stops simulated time and new traffic. Restarting the API loses in-memory runs. To run backend tests, from the repository root use:

```powershell
backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q backend/tests
```

For a guided research workflow, open **Metrics & comparison**. It starts with the baseline preset selected; choose the observation cutoff and 1, 3, or 5 consecutive seeds, run the matched routing study, then download the run-level CSV. See [`docs/final-evaluation.md`](docs/final-evaluation.md) for the recommended method, interpretation, and limitations.

For Unix-like shells, replace `backend/.venv/Scripts/python.exe` with `backend/.venv/bin/python`. Run Python commands through this virtual environment.
