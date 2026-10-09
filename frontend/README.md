# LEO-DTN dashboard

The dashboard is a Next.js client for the local FastAPI service. It submits a complete node/contact/bundle configuration to the API, then renders the engine's returned state. Configuration edits apply to the next run; the dashboard does not make routing or contact-availability decisions.

## Run locally

From the repository root, start the backend in one terminal:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn leo_dtn.api:app --app-dir backend --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The default API URL is `http://127.0.0.1:8000`. Set `NEXT_PUBLIC_API_URL` in `.env.local` to override it; `.env.example` shows the local default.

## First-view behavior

- Manually add satellites with scene-frame XYZ coordinates in kilometers, or add a seeded set of positions. Repeating the same seed/count generates the same coordinates.
- Add explicit directed contact windows to connect nodes. A newly added satellite is visible immediately in the next run; it forwards bundles only when the supplied contact plan makes a path available.
- The Earth mesh remains at the origin and is never animated. Dragging rotates the camera around the scene. Packet-follow moves the camera target to the selected bundle's engine-derived position.
- The packet marker interpolates only while the API reports a real active transmission; while queued it stays at its engine-reported holder. The first version does not animate satellite motion or generate orbital contacts.

The first dashboard uses a procedural local globe texture and Three.js `OrbitControls`. The globe is an illustrative scene surface; configured XYZ coordinates and contact schedules are the simulation inputs. The scene does not imply orbital fidelity.
