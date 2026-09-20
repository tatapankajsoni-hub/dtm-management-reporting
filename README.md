# Tata Motors DTM — PostgreSQL-Native Main Application

This package is the main Tata Motors Driver Training application. The browser talks to the same-origin FastAPI service, and FastAPI reads/writes the existing PostgreSQL DTM schema. No Supabase dependency is used.

## Render
- Service type: Web Service (not Static Site)
- Root Directory: blank
- Build: `pip install -r requirements.txt`
- Start: `python -c "import os,uvicorn; uvicorn.run(\'main:app\',host=\'0.0.0.0\',port=int(os.environ.get(\'PORT\',\'10000\')))"`
- Environment: `DATABASE_URL` = existing Render PostgreSQL Internal Database URL; `PYTHON_VERSION=3.13.5`

## Routes
- `/` driver training app
- `/health` health check
- `/api/workshops` active workshop master
- `/api/drivers/register` registration + M1-M4 initialization
- `/api/drivers/{id}/topics` training session logging
- `/api/drivers/{id}/modules/{module}/pretest` module completion
- `/api/drivers/{id}/final` final assessment
- `/api/drivers/{id}/certificate` certificate

The production PostgreSQL schema is not created or altered by this service.
