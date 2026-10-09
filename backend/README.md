# Python backend

The simulation engine is a standalone Python package under `leo_dtn/`; it does not require FastAPI. Run its tests with the project virtual environment.

From the repository root in PowerShell:

```powershell
uv venv --seed --python 3.14 backend/.venv
uv pip install --python backend/.venv/Scripts/python.exe -e "backend[test]"
backend/.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml -q backend/tests
```

To run the local API from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn leo_dtn.api:app --app-dir backend --reload
```

From the repository root on Unix-like shells, use `backend/.venv/bin/python` for the pytest command. Keep all subsequent Python commands inside this environment.
