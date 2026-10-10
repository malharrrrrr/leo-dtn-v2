# LEO-DTN contributor instructions

## Project identity

LEO-DTN is an academic simulator and visualization platform for store-carry-forward networking over time-dependent contacts in a Low Earth Orbit (LEO) satellite network. It is a simulator, not an operational communications system.

## Locked stack

- Frontend: TypeScript, Next.js, and React.
- API: Python, FastAPI, and Pydantic.
- Simulation: deterministic, discrete-event Python engine.
- Tests: pytest for Python; appropriate TypeScript type checking, linting, and frontend tests.
- Initial state is in memory; scenario and result exports are JSON and CSV.
- Local single-laptop runtime. Do not add a database or distributed infrastructure without a concrete requirement.

## Boundaries that must hold

- The simulation engine is the single source of truth for simulation state.
- The engine has no HTTP, frontend, or wall-clock dependency and must be callable directly from Python.
- FastAPI validates commands, invokes the engine, and returns read-only response models. It does not contain simulation rules.
- The frontend renders engine-returned state. It must not implement routing, contact scheduling, or bundle forwarding.
- Routing strategies can change without changing event scheduling or transmission lifecycle semantics.
- Exports and API responses must not expose mutable engine-owned objects.

## Working practices

- Read `PROJECT.md`, `docs/architecture.md`, and `docs/simulation-model.md` before changing the corresponding design or behavior.
- Keep documented behavior, modelling assumptions, and future work distinct. Do not claim full Bundle Protocol compliance, operational validity, or high-fidelity orbital propagation without implementing and validating it.
- Preserve deterministic replay: explicit scenario/configuration/seed, stable event ordering, and no wall-clock reads in engine decisions.
- Add or update focused tests for changed behavior. Run relevant pytest, type-check, lint, and frontend checks when implementation exists; report commands and outcomes accurately.
- Tests must exercise the engine without requiring FastAPI or the frontend where the engine is under test.
- Run every Python command through the project virtual environment: `backend/.venv/Scripts/python.exe` on Windows or `backend/.venv/bin/python` on Unix. Do not fall back to the system Python after the venv exists.
- Update the relevant specification and `ROADMAP.md` when scope, semantics, API contracts, or acceptance criteria change.
- Keep `HANDOFF.md` current after substantial work: update checkout state, verified commands, known issues, and the next useful task for an incoming agent.
- Keep changes focused. Avoid placeholder modules, speculative abstractions, unrelated cleanup, and dependencies without a demonstrated need.
- Do not install dependencies or initialize application scaffolding without a project task that calls for implementation.

## Implementation order

Follow `ROADMAP.md` and keep its milestone status current. Circular satellite motion and geometry-derived link windows are core requirements for the dashboard: use the documented simplified two-body model and spherical Earth, and do not present static placements as moving LEO satellites. Do not claim high-fidelity orbital or RF behavior.
