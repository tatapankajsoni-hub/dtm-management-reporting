import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ============================================================
# TATA MOTORS DTM - MANAGEMENT REPORTING
# FINAL POSTGRESQL VERSION
#
# READ ONLY:
# - Does NOT create/alter tables
# - Does NOT seed data
# - Does NOT write driver data
# - Uses the same Render PostgreSQL DATABASE_URL as the DTM app
# ============================================================

RAW_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not RAW_DATABASE_URL:
    DATABASE_URL = ""
elif RAW_DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = RAW_DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif RAW_DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = RAW_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = RAW_DATABASE_URL

ADMIN_KEY = os.getenv("DTM_ADMIN_KEY", "").strip()
MODULES = {
    "M1": "Road Safety",
    "M2": "Vehicle Knowledge",
    "M3": "Fuel & Tyres",
    "M4": "BS6 Technology",
}

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
else:
    engine = None
    SessionLocal = None

app = FastAPI(
    title="Tata Motors DTM Management Reporting",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent
# Flat repository layout: index.html is deployed at the repository root.
# Keep dashboard/ as a fallback for older deployments.
DASHBOARD = ROOT / "index.html"
if not DASHBOARD.exists():
    DASHBOARD = ROOT / "dashboard" / "index.html"


def get_db():
    if SessionLocal is None:
        raise HTTPException(503, "DATABASE_URL is not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_dtm_admin: Optional[str] = Header(None)):
    if not ADMIN_KEY:
        raise HTTPException(503, "DTM_ADMIN_KEY is not configured")
    if not x_dtm_admin or x_dtm_admin != ADMIN_KEY:
        raise HTTPException(401, "Admin authentication required")


def parse_date(value: Optional[str], end=False):
    if not value:
        return None
    try:
        if len(value) == 10:
            dt = datetime.fromisoformat(value)
            if end:
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(400, f"Invalid date: {value}. Use YYYY-MM-DD.")


def dt_json(v):
    return v.isoformat() if v else None


def pct(n, d):
    return round((float(n) / float(d)) * 100, 1) if d else 0.0


def filters_clause(from_date, to_date, workshop_code=None, sso=None, partner_type=None, alias="d"):
    clauses = []
    params = {}
    if from_date:
        clauses.append(f"{alias}.registration_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        clauses.append(f"{alias}.registration_date <= :to_date")
        params["to_date"] = to_date
    if workshop_code:
        clauses.append("COALESCE(w.workshop_code, '') = :workshop_code")
        params["workshop_code"] = workshop_code
    if sso:
        clauses.append("COALESCE(w.sso, '') = :sso")
        params["sso"] = sso
    if partner_type:
        clauses.append("COALESCE(w.partner_type, '') = :partner_type")
        params["partner_type"] = partner_type
    return (" AND ".join(clauses) if clauses else "TRUE"), params


def scope_values(from_date, to_date, workshop_code, sso, partner_type):
    fd = parse_date(from_date)
    td = parse_date(to_date, end=True)
    if fd and td and fd > td:
        raise HTTPException(400, "from_date cannot be after to_date")
    return fd, td, workshop_code, sso, partner_type


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("""
                SELECT
                    current_database() AS database_name,
                    current_schema() AS schema_name,
                    (SELECT COUNT(*) FROM public.workshops) AS workshops,
                    (SELECT COUNT(*) FROM public.drivers) AS drivers,
                    (SELECT COUNT(*) FROM public.module_progress) AS module_progress,
                    (SELECT COUNT(*) FROM public.training_sessions) AS training_sessions,
                    (SELECT COUNT(*) FROM public.final_assessment) AS final_assessment,
                    (SELECT COUNT(*) FROM public.certificates) AS certificates
            """)
        ).mappings().one()
        return {
            "ok": True,
            "service": "DTM Management Reporting",
            "version": "3.0.0",
            "database": "connected",
            "database_name": row["database_name"],
            "schema": row["schema_name"],
            "counts": {
                "workshops": row["workshops"],
                "drivers": row["drivers"],
                "module_progress": row["module_progress"],
                "training_sessions": row["training_sessions"],
                "final_assessment": row["final_assessment"],
                "certificates": row["certificates"],
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "service": "DTM Management Reporting",
            "version": "3.0.0",
            "database": "error",
            "detail": str(e),
        }


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(DASHBOARD)


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD)


@app.get("/api/admin/filters", dependencies=[Depends(require_admin)])
def filters(db: Session = Depends(get_db)):
    ssos = [
        r[0] for r in db.execute(
            text("""
                SELECT DISTINCT sso
                FROM public.workshops
                WHERE is_active = TRUE AND sso IS NOT NULL AND TRIM(sso) <> ''
                ORDER BY sso
            """)
        ).all()
    ]
    partners = [
        r[0] for r in db.execute(
            text("""
                SELECT DISTINCT partner_type
                FROM public.workshops
                WHERE is_active = TRUE AND partner_type IS NOT NULL AND TRIM(partner_type) <> ''
                ORDER BY partner_type
            """)
        ).all()
    ]
    cities = [
        r[0] for r in db.execute(
            text("""
                SELECT DISTINCT city
                FROM public.workshops
                WHERE is_active = TRUE AND city IS NOT NULL AND TRIM(city) <> ''
                ORDER BY city
            """)
        ).all()
    ]
    workshops = db.execute(
        text("""
            SELECT workshop_code, workshop_name, city
            FROM public.workshops
            WHERE is_active = TRUE
            ORDER BY workshop_name
        """)
    ).mappings().all()
    return {
        "ssos": ssos,
        "partner_types": partners,
        "cities": cities,
        "modules": [{"code": k, "name": v} for k, v in MODULES.items()],
        "workshops": [dict(x) for x in workshops],
    }


@app.get("/api/admin/debug/endpoint-check", dependencies=[Depends(require_admin)])
def endpoint_check(db: Session = Depends(get_db)):
    checks = {}
    tests = {
        "workshops": "SELECT COUNT(*) FROM public.workshops",
        "drivers": "SELECT COUNT(*) FROM public.drivers",
        "module_progress": "SELECT COUNT(*) FROM public.module_progress",
        "training_sessions": "SELECT COUNT(*) FROM public.training_sessions",
        "final_assessment": "SELECT COUNT(*) FROM public.final_assessment",
        "certificates": "SELECT COUNT(*) FROM public.certificates",
        "filters_workshops": "SELECT COUNT(*) FROM public.workshops WHERE is_active = TRUE",
        "driver_workshop_join": "SELECT COUNT(*) FROM public.drivers d LEFT JOIN public.workshops w ON w.id=d.workshop_id",
        "module_driver_join": "SELECT COUNT(*) FROM public.module_progress mp JOIN public.drivers d ON d.id=mp.driver_id",
        "certificate_driver_join": "SELECT COUNT(*) FROM public.certificates c JOIN public.drivers d ON d.id=c.driver_id",
        "assessment_driver_join": "SELECT COUNT(*) FROM public.final_assessment fa JOIN public.drivers d ON d.id=fa.driver_id",
    }
    for name,q in tests.items():
        try:
            checks[name] = {"ok": True, "count": int(db.execute(text(q)).scalar() or 0)}
        except Exception as e:
            checks[name] = {"ok": False, "error": str(e)}
            db.rollback()
    return {"ok": all(v["ok"] for v in checks.values()), "checks": checks}

@app.get("/api/admin/debug/counts", dependencies=[Depends(require_admin)])
def debug_counts(db: Session = Depends(get_db)):
    r = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM public.workshops) AS workshops,
                (SELECT COUNT(*) FROM public.drivers) AS drivers,
                (SELECT COUNT(*) FROM public.module_progress) AS module_progress,
                (SELECT COUNT(*) FROM public.training_sessions) AS training_sessions,
                (SELECT COUNT(*) FROM public.final_assessment) AS final_assessment,
                (SELECT COUNT(*) FROM public.certificates) AS certificates,
                (SELECT MAX(registration_date) FROM public.drivers) AS latest_driver_registration
        """)
    ).mappings().one()
    return {
        "workshops": r["workshops"],
        "drivers": r["drivers"],
        "module_progress": r["module_progress"],
        "training_sessions": r["training_sessions"],
        "final_assessment": r["final_assessment"],
        "certificates": r["certificates"],
        "latest_driver_registration": dt_json(r["latest_driver_registration"]),
    }


@app.get("/api/admin/dashboard", dependencies=[Depends(require_admin)])
def dashboard_api(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    workshop_code: Optional[str] = None,
    sso: Optional[str] = None,
    partner_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    fd, td, wc, ss, pt = scope_values(from_date, to_date, workshop_code, sso, partner_type)
    where, params = filters_clause(fd, td, wc, ss, pt)

    row = db.execute(
        text(f"""
            SELECT
                COUNT(DISTINCT d.id) AS registered,
                COUNT(DISTINCT CASE
                    WHEN COALESCE(d.overall_status, '') <> 'Registered'
                      OR d.last_activity IS DISTINCT FROM d.registration_date
                      OR EXISTS (
                          SELECT 1 FROM public.module_progress mp2
                          WHERE mp2.driver_id = d.id
                            AND (mp2.started_at IS NOT NULL OR COALESCE(mp2.pretest_attempts,0) > 0)
                      )
                    THEN d.id END) AS started,
                COUNT(DISTINCT CASE
                    WHEN COALESCE(d.completion_percentage,0) >= 100
                      OR (
                          SELECT COUNT(DISTINCT mp3.module_code)
                          FROM public.module_progress mp3
                          WHERE mp3.driver_id = d.id
                            AND LOWER(COALESCE(mp3.status,'')) = 'completed'
                      ) >= 4
                    THEN d.id END) AS completed,
                COUNT(DISTINCT CASE
                    WHEN d.certificate_id IS NOT NULL
                      OR EXISTS (SELECT 1 FROM public.certificates c2 WHERE c2.driver_id = d.id)
                    THEN d.id END) AS certified
            FROM public.drivers d
            LEFT JOIN public.workshops w ON w.id = d.workshop_id
            WHERE {where}
        """),
        params,
    ).mappings().one()

    total_workshops = db.execute(
        text("SELECT COUNT(*) FROM public.workshops WHERE is_active = TRUE")
    ).scalar() or 0

    adopted_workshops = db.execute(
        text(f"""
            SELECT COUNT(DISTINCT w.id)
            FROM public.workshops w
            WHERE w.is_active = TRUE
              AND EXISTS (
                  SELECT 1
                  FROM public.drivers d
                  WHERE d.workshop_id = w.id
                    AND {filters_clause(fd, td, None, ss, pt, "d")[0]}
              )
        """),
        {k: v for k, v in params.items() if k in ("from_date", "to_date", "sso", "partner_type")},
    ).scalar() or 0

    attempts = db.execute(
        text(f"""
            SELECT COUNT(*)
            FROM public.final_assessment fa
            JOIN public.drivers d ON d.id = fa.driver_id
            LEFT JOIN public.workshops w ON w.id = d.workshop_id
            WHERE {where}
        """),
        params,
    ).scalar() or 0

    passed = db.execute(
        text(f"""
            SELECT COUNT(DISTINCT fa.driver_id)
            FROM public.final_assessment fa
            JOIN public.drivers d ON d.id = fa.driver_id
            LEFT JOIN public.workshops w ON w.id = d.workshop_id
            WHERE {where}
              AND LOWER(COALESCE(fa.status,'')) = 'passed'
        """),
        params,
    ).scalar() or 0

    total = int(row["registered"] or 0)
    completed = int(row["completed"] or 0)
    certified = int(row["certified"] or 0)
    started = int(row["started"] or 0)

    return {
        "filters": {
            "from_date": from_date,
            "to_date": to_date,
            "workshop_code": wc,
            "sso": ss,
            "partner_type": pt,
        },
        "kpis": {
            "registered_drivers": total,
            "training_started": started,
            "training_completed": completed,
            "in_progress": max(total - completed, 0),
            "certified_drivers": certified,
            "certification_rate": pct(certified, total),
            "total_workshops": int(total_workshops),
            "active_workshops": int(adopted_workshops),
            "inactive_workshops": max(int(total_workshops) - int(adopted_workshops), 0),
            "workshop_adoption_rate": pct(adopted_workshops, total_workshops),
            "final_assessment_attempts": int(attempts),
            "final_passed_drivers": int(passed),
            "final_pass_rate": pct(passed, attempts),
        },
    }


@app.get("/api/admin/module-progress", dependencies=[Depends(require_admin)])
def module_progress(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    workshop_code: Optional[str] = None,
    sso: Optional[str] = None,
    partner_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    fd, td, wc, ss, pt = scope_values(from_date, to_date, workshop_code, sso, partner_type)
    where, params = filters_clause(fd, td, wc, ss, pt)

    total = db.execute(
        text(f"""
            SELECT COUNT(DISTINCT d.id)
            FROM public.drivers d
            LEFT JOIN public.workshops w ON w.id = d.workshop_id
            WHERE {where}
        """),
        params,
    ).scalar() or 0

    out = []
    for code, name in MODULES.items():
        r = db.execute(
            text(f"""
                SELECT
                    COUNT(DISTINCT mp.driver_id) FILTER (
                        WHERE mp.started_at IS NOT NULL OR COALESCE(mp.pretest_attempts,0) > 0
                    ) AS started,
                    COUNT(DISTINCT mp.driver_id) FILTER (
                        WHERE LOWER(COALESCE(mp.status,'')) = 'completed'
                    ) AS completed,
                    COALESCE(SUM(COALESCE(mp.pretest_attempts,0)),0) AS attempts,
                    COALESCE(AVG(mp.pretest_percentage) FILTER (
                        WHERE COALESCE(mp.pretest_attempts,0) > 0
                    ),0) AS avg_pretest
                FROM public.module_progress mp
                JOIN public.drivers d ON d.id = mp.driver_id
                LEFT JOIN public.workshops w ON w.id = d.workshop_id
                WHERE mp.module_code = :module_code
                  AND {where}
            """),
            {**params, "module_code": code},
        ).mappings().one()

        started = int(r["started"] or 0)
        completed = int(r["completed"] or 0)
        out.append({
            "module_code": code,
            "module_name": name,
            "registered": int(total),
            "started": started,
            "completed": completed,
            "not_started": max(int(total) - started, 0),
            "completion_rate": pct(completed, total),
            "start_rate": pct(started, total),
            "pretest_attempts": int(r["attempts"] or 0),
            "average_pretest_percentage": round(float(r["avg_pretest"] or 0), 1),
        })
    return out


@app.get("/api/admin/workshop-adoption", dependencies=[Depends(require_admin)])
def workshop_adoption(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sso: Optional[str] = None,
    partner_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    fd, td, _, ss, pt = scope_values(from_date, to_date, None, sso, partner_type)
    params = {"from_date": fd, "to_date": td, "sso": ss, "partner_type": pt}
    filters = ["d.workshop_id = w.id"]
    if fd:
        filters.append("d.registration_date >= :from_date")
    if td:
        filters.append("d.registration_date <= :to_date")

    out = []
    workshops = db.execute(
        text("""
            SELECT id, workshop_code, workshop_name, city, sso, region, partner_type
            FROM public.workshops
            WHERE is_active = TRUE
              AND (:sso IS NULL OR sso = :sso)
              AND (:partner_type IS NULL OR partner_type = :partner_type)
            ORDER BY workshop_name
        """),
        params,
    ).mappings().all()

    for w in workshops:
        q = f"""
            SELECT
                COUNT(*) AS registered,
                COUNT(*) FILTER (
                    WHERE COALESCE(d.overall_status,'') <> 'Registered'
                       OR EXISTS (
                           SELECT 1 FROM public.module_progress mp
                           WHERE mp.driver_id = d.id
                             AND (mp.started_at IS NOT NULL OR COALESCE(mp.pretest_attempts,0) > 0)
                       )
                ) AS started,
                COUNT(*) FILTER (
                    WHERE COALESCE(d.completion_percentage,0) >= 100
                       OR (
                           SELECT COUNT(DISTINCT mp2.module_code)
                           FROM public.module_progress mp2
                           WHERE mp2.driver_id = d.id
                             AND LOWER(COALESCE(mp2.status,'')) = 'completed'
                       ) >= 4
                ) AS completed,
                COUNT(*) FILTER (
                    WHERE d.certificate_id IS NOT NULL
                       OR EXISTS (SELECT 1 FROM public.certificates c WHERE c.driver_id = d.id)
                ) AS certified
            FROM public.drivers d
            WHERE d.workshop_id = :workshop_id
              AND (:from_date IS NULL OR d.registration_date >= :from_date)
              AND (:to_date IS NULL OR d.registration_date <= :to_date)
        """
        r = db.execute(text(q), {**params, "workshop_id": w["id"]}).mappings().one()
        registered = int(r["registered"] or 0)
        out.append({
            "workshop_code": w["workshop_code"],
            "workshop_name": w["workshop_name"],
            "city": w["city"],
            "sso": w["sso"],
            "region": w["region"],
            "partner_type": w["partner_type"],
            "registered": registered,
            "started": int(r["started"] or 0),
            "completed": int(r["completed"] or 0),
            "certified": int(r["certified"] or 0),
            "adoption_status": "Active" if registered else "Not Started",
            "adoption_percent": 100 if registered else 0,
        })
    return out


@app.get("/api/admin/certifications", dependencies=[Depends(require_admin)])
def certifications(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    workshop_code: Optional[str] = None,
    sso: Optional[str] = None,
    partner_type: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    fd, td, wc, ss, pt = scope_values(from_date, to_date, workshop_code, sso, partner_type)
    clauses = ["1=1"]
    params = {"limit": limit}
    if fd:
        clauses.append("c.completion_date >= :from_date"); params["from_date"] = fd
    if td:
        clauses.append("c.completion_date <= :to_date"); params["to_date"] = td
    if wc:
        clauses.append("w.workshop_code = :workshop_code"); params["workshop_code"] = wc
    if ss:
        clauses.append("w.sso = :sso"); params["sso"] = ss
    if pt:
        clauses.append("w.partner_type = :partner_type"); params["partner_type"] = pt

    rows = db.execute(
        text(f"""
            SELECT
                c.certificate_id,
                d.driver_id,
                c.driver_name,
                d.mobile_number,
                c.vehicle_number,
                d.vehicle_model,
                c.workshop_name,
                w.sso,
                c.final_score,
                c.final_percentage,
                c.completion_date,
                c.certificate_url
            FROM public.certificates c
            JOIN public.drivers d ON d.id = c.driver_id
            LEFT JOIN public.workshops w ON w.id = d.workshop_id
            WHERE {' AND '.join(clauses)}
            ORDER BY c.completion_date DESC
            LIMIT :limit
        """),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/api/admin/drivers-report", dependencies=[Depends(require_admin)])
def drivers_report(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    workshop_code: Optional[str] = None,
    sso: Optional[str] = None,
    partner_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    fd, td, wc, ss, pt = scope_values(from_date, to_date, workshop_code, sso, partner_type)
    clauses = ["1=1"]
    params = {"limit": limit}
    if fd:
        clauses.append("d.registration_date >= :from_date"); params["from_date"] = fd
    if td:
        clauses.append("d.registration_date <= :to_date"); params["to_date"] = td
    if wc:
        clauses.append("w.workshop_code = :workshop_code"); params["workshop_code"] = wc
    if ss:
        clauses.append("w.sso = :sso"); params["sso"] = ss
    if pt:
        clauses.append("w.partner_type = :partner_type"); params["partner_type"] = pt
    if search and search.strip():
        params["search"] = f"%{search.strip()}%"
        clauses.append("""
            (
                d.full_name ILIKE :search
                OR d.mobile_number ILIKE :search
                OR d.vehicle_number ILIKE :search
                OR d.driver_id ILIKE :search
                OR d.licence_number ILIKE :search
            )
        """)

    rows = db.execute(
        text(f"""
            SELECT
                d.id,
                d.driver_id,
                d.full_name,
                d.mobile_number,
                d.licence_number,
                d.vehicle_number,
                d.vehicle_model,
                d.workshop_name,
                w.sso,
                w.partner_type,
                d.overall_status,
                d.completion_percentage,
                d.registration_date,
                d.last_activity,
                d.certificate_id
            FROM public.drivers d
            LEFT JOIN public.workshops w ON w.id = d.workshop_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.registration_date DESC
            LIMIT :limit
        """),
        params,
    ).mappings().all()

    result = []
    for d in rows:
        mods = db.execute(
            text("""
                SELECT module_code, status, pretest_percentage, completed_at
                FROM public.module_progress
                WHERE driver_id = :driver_id
                ORDER BY module_code
            """),
            {"driver_id": d["id"]},
        ).mappings().all()
        md = {
            m["module_code"]: {
                "status": m["status"],
                "pretest_percentage": float(m["pretest_percentage"] or 0),
                "completed_at": dt_json(m["completed_at"]),
            }
            for m in mods
        }
        final = db.execute(
            text("""
                SELECT score, percentage, status
                FROM public.final_assessment
                WHERE driver_id = :driver_id
                ORDER BY attempt_number DESC, completed_at DESC NULLS LAST
                LIMIT 1
            """),
            {"driver_id": d["id"]},
        ).mappings().first()

        result.append({
            "driver_id": d["driver_id"],
            "full_name": d["full_name"],
            "mobile_number": d["mobile_number"],
            "licence_number": d["licence_number"],
            "vehicle_number": d["vehicle_number"],
            "vehicle_model": d["vehicle_model"],
            "workshop_name": d["workshop_name"],
            "sso": d["sso"],
            "partner_type": d["partner_type"],
            "status": d["overall_status"],
            "completion_percentage": float(d["completion_percentage"] or 0),
            "registration_date": dt_json(d["registration_date"]),
            "last_activity": dt_json(d["last_activity"]),
            "certificate_id": d["certificate_id"],
            "final_score": final["score"] if final else None,
            "final_percentage": float(final["percentage"]) if final else None,
            "final_status": final["status"] if final else None,
            "modules": md,
        })
    return result


@app.get("/api/admin/daily-trend", dependencies=[Depends(require_admin)])
def daily_trend(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for i in range(days - 1, -1, -1):
        start = today - timedelta(days=i)
        end = start + timedelta(days=1)
        p = {"start": start, "end": end}
        registered = db.execute(
            text("SELECT COUNT(*) FROM public.drivers WHERE registration_date >= :start AND registration_date < :end"), p
        ).scalar() or 0
        certified = db.execute(
            text("SELECT COUNT(*) FROM public.certificates WHERE completion_date >= :start AND completion_date < :end"), p
        ).scalar() or 0
        assessments = db.execute(
            text("SELECT COUNT(*) FROM public.final_assessment WHERE completed_at >= :start AND completed_at < :end"), p
        ).scalar() or 0
        module_completions = db.execute(
            text("SELECT COUNT(*) FROM public.module_progress WHERE completed_at >= :start AND completed_at < :end"), p
        ).scalar() or 0
        out.append({
            "date": start.date().isoformat(),
            "registered": int(registered),
            "certified": int(certified),
            "assessments": int(assessments),
            "module_completions": int(module_completions),
        })
    return out


@app.get("/api/admin/export/drivers.csv", dependencies=[Depends(require_admin)])
def export_drivers(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    workshop_code: Optional[str] = None,
    sso: Optional[str] = None,
    partner_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    data = drivers_report(
        from_date=from_date,
        to_date=to_date,
        workshop_code=workshop_code,
        sso=sso,
        partner_type=partner_type,
        search=None,
        limit=5000,
        db=db,
    )
    lines = [
        "Driver ID,Name,Mobile,Licence,Vehicle,Model,Workshop,SSO,Partner,Status,Completion %,Certificate,Final %"
    ]
    for x in data:
        vals = [
            x["driver_id"], x["full_name"], x["mobile_number"], x["licence_number"],
            x["vehicle_number"], x["vehicle_model"], x["workshop_name"], x["sso"],
            x["partner_type"], x["status"], x["completion_percentage"],
            x["certificate_id"] or "",
            x["final_percentage"] if x["final_percentage"] is not None else "",
        ]
        lines.append(",".join('"' + str(v or "").replace('"', '""') + '"' for v in vals))

    return StreamingResponse(
        iter(["\n".join(lines)]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=DTM_Driver_MIS.csv"},
    )
