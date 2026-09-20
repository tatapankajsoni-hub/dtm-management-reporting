# DTM Management Reporting — Read-only service

This is a separate FastAPI + PostgreSQL reporting service for the Tata Motors Driver Training (DTM) application. It **does not modify the frozen driver application** and does not call `create_all()` or seed the database.

## Deploy on Render
1. Create a new Web Service from this folder/repository.
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add `DATABASE_URL` = the **same PostgreSQL connection string used by the existing DTM driver API**.
5. Add `DTM_ADMIN_KEY` = a new strong management-only key.
6. Open `/dashboard`.

## APIs
- GET `/health`
- GET `/api/admin/filters`
- GET `/api/admin/dashboard`
- GET `/api/admin/module-progress`
- GET `/api/admin/workshop-adoption`
- GET `/api/admin/certifications`
- GET `/api/admin/drivers-report`
- GET `/api/admin/daily-trend`
- GET `/api/admin/export/drivers.csv`

All reporting endpoints require `X-DTM-Admin: <DTM_ADMIN_KEY>`.

## Metrics
- Drivers registered
- Training started
- Training completed (all 4 modules)
- In progress
- Certified drivers
- Certification rate
- Active / not-yet-adopted workshops
- Workshop-wise registration, started, completed and certified counts
- M1–M4 progress and average pre-test score
- Final assessment attempts/pass rate
- Daily registration, module completion, assessment and certification trend
- Driver-level MIS

The four reporting modules are aligned with the DTM program structure: Road Safety, Vehicle Knowledge, Fuel & Tyres, and BS6 Technology.
