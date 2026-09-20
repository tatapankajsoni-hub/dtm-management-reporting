# TATA DTM Management Reporting — Supabase Live v3

This is the management reporting service for the frozen Tata Motors DTM driver application.

## Architecture

The driver application writes driver, module, session, assessment and certificate data to the DTM Supabase PostgreSQL database. This service reads that SAME PostgreSQL database directly. No data replication or scheduled sync is used.

```text
Driver App -> Supabase PostgreSQL <- Management Reporting API <- Management Dashboard
```

## Important: DATABASE_URL

Set Render environment variable `DATABASE_URL` to the PostgreSQL connection string for the SAME Supabase project used by the driver application.

Prefer the Supabase **Session Pooler** connection string for a hosted Render service. Keep the password URL-encoded. The application automatically adds `sslmode=require` when it is absent.

Do NOT put a Supabase service-role/secret key in the browser. The management browser only sends `X-DTM-Admin`.

## Render

Root Directory: blank
Build Command: `pip install -r requirements.txt`
Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
Python: `3.13.5`

Environment:
- `DATABASE_URL` = SAME Supabase PostgreSQL connection string used by DTM
- `DTM_ADMIN_KEY` = management-only secret
- `PYTHON_VERSION` = `3.13.5`

## Verification

Open `/health`. Expected:

```json
{"ok":true,"service":"DTM Management Reporting","version":"3.0.0","database":"connected","database_source":"supabase_postgresql"}
```

Then open `/dashboard` and authenticate with the management API key.

## Read-only safety

This service does NOT call `create_all()`, does NOT seed workshops, and exposes no driver write endpoint. It only reads the existing DTM tables.
