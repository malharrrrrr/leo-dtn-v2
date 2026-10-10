# LEO-DTN dashboard

The Next.js dashboard configures and inspects local simulations through the FastAPI service. The Python engine supplies all satellite positions, generated contact windows, active transmissions, bundle status, and metrics. The 3D view keeps the Earth fixed while satellites move in the engine's circular-orbit model; users can rotate the camera, inspect node details, and follow a selected bundle.

## Run locally

From the repository root, start the API in one terminal:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn leo_dtn.api:app --app-dir backend --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API defaults to `http://127.0.0.1:8000`; set `NEXT_PUBLIC_API_URL` in `.env.local` to override it.

Satellite placement is configured with altitude, inclination, RAAN, and phase, or seeded randomized orbital elements. Contact generation is based on sampled geometry with a configured minimum ground-station elevation. It uses a circular two-body model and spherical Earth, and does not include perturbations, antenna patterns, or a radio link budget.
