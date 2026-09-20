# TATA DTM Management Reporting — Final PostgreSQL Version

This package is the management/reporting service for the DTM driver application.

## Architecture

Driver application -> same Render PostgreSQL database -> Management Reporting API -> Management Dashboard

There is NO Supabase dependency and NO second database.

## Important

The reporting service is read-only. It does not:
- create tables
- alter schema
- seed workshops
- write driver records
- modify the driver application

## Render environment variables

Set these on the management-reporting Render service:

DATABASE_URL
: Use the SAME PostgreSQL connection string/database used by the live DTM driver application. Prefer the Render PostgreSQL Internal Database URL when both services are in the same Render region.

DTM_ADMIN_KEY
: Management-only secret used by the dashboard X-DTM-Admin header.

PYTHON_VERSION
: 3.13.5

## Render settings

Build:
pip install -r requirements.txt

Start:
uvicorn main:app --host 0.0.0.0 --port $PORT

## Verification

1. Open /health.
2. Confirm `"database":"connected"`.
3. Confirm counts for workshops/drivers/module_progress/etc.
4. Open /dashboard.
5. Enter the management API URL and DTM_ADMIN_KEY.
6. Register a new driver in the DTM application.
7. Press Refresh in the management dashboard.

The dashboard reads live PostgreSQL data on every refresh.

## Debug endpoint

Authenticated:
GET /api/admin/debug/counts

This exposes only table counts and the latest driver registration timestamp. It is useful for confirming that the management service sees fresh application entries.

## Expected tables

public.workshops
public.drivers
public.module_progress
public.training_sessions
public.final_assessment
public.certificates

The 99-workshop master is read directly from public.workshops. No CSV is required by the management service.


## v3.2 diagnostics
The dashboard now reports the exact API endpoint and HTTP error instead of hiding a failing section. Authenticated `/api/admin/debug/endpoint-check` checks the live table/join queries without modifying data.
