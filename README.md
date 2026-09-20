# TATA_DTM — Management Reporting Service

A separate FastAPI + PostgreSQL **read-only management reporting service** for the Tata Motors Driver Training (DTM) application.

## Files

- `main.py` — complete FastAPI reporting application.
- `index.py` — thin Render/Uvicorn entrypoint that imports `app` from `main.py`.
- `dashboard/index.html` — management dashboard UI.
- `requirements.txt` — Python dependencies.
- `Dockerfile` — optional container deployment.
- `render.yaml` — Render service configuration.

## Render deployment

Use the repository contents directly. Do not upload the ZIP to Render as a runtime source.

Recommended Render settings:

- Runtime: Python
- Python: 3.13.5 via `PYTHON_VERSION`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn index:app --host 0.0.0.0 --port $PORT`
- `DATABASE_URL`: the existing DTM PostgreSQL **Internal Database URL**
- `DTM_ADMIN_KEY`: a new management-only secret

Do not create a new database and do not modify the frozen driver application database schema for this reporting service.

## Endpoints

- `/health`
- `/dashboard`
- `/api/admin/filters`
- `/api/admin/dashboard`
- `/api/admin/module-progress`
- `/api/admin/workshop-adoption`
- `/api/admin/certifications`
- `/api/admin/drivers-report`
- `/api/admin/daily-trend`
- `/api/admin/export/drivers.csv`

All `/api/admin/*` endpoints require the `X-DTM-Admin` header.
