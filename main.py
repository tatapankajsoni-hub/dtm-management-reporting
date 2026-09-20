import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import create_engine, String, Boolean, DateTime, Integer, Numeric, ForeignKey, select, func, or_, case, and_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

# READ-ONLY reporting service.
# It deliberately does NOT call Base.metadata.create_all(), seed data, or expose driver write APIs.
# This protects the frozen driver application and only reads the existing DTM PostgreSQL database.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dtm.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Workshop(Base):
    __tablename__ = "workshops"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_code: Mapped[Optional[str]] = mapped_column(String(100))
    workshop_code: Mapped[str] = mapped_column(String(100))
    workshop_name: Mapped[str] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(120))
    state: Mapped[Optional[str]] = mapped_column(String(80))
    sso: Mapped[Optional[str]] = mapped_column(String(120))
    region: Mapped[Optional[str]] = mapped_column(String(120))
    workshop_division: Mapped[Optional[str]] = mapped_column(String(120))
    partner_type: Mapped[Optional[str]] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean)

class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    driver_id: Mapped[str] = mapped_column(String(80))
    full_name: Mapped[str] = mapped_column(String(200))
    mobile_number: Mapped[str] = mapped_column(String(20))
    licence_number: Mapped[str] = mapped_column(String(100))
    vehicle_number: Mapped[str] = mapped_column(String(50))
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(150))
    workshop_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workshops.id"))
    workshop_name: Mapped[Optional[str]] = mapped_column(String(255))
    dealer_name: Mapped[Optional[str]] = mapped_column(String(255))
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    overall_status: Mapped[str] = mapped_column(String(50))
    completion_percentage: Mapped[float] = mapped_column(Numeric(5,2))
    completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    certificate_id: Mapped[Optional[str]] = mapped_column(String(120))

class ModuleProgress(Base):
    __tablename__ = "module_progress"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"))
    module_code: Mapped[str] = mapped_column(String(20))
    module_name: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50))
    pretest_score: Mapped[int] = mapped_column(Integer)
    pretest_total: Mapped[int] = mapped_column(Integer)
    pretest_percentage: Mapped[float] = mapped_column(Numeric(5,2))
    pretest_attempts: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class TrainingSession(Base):
    __tablename__ = "training_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"))
    module_code: Mapped[str] = mapped_column(String(20))
    topic_code: Mapped[Optional[str]] = mapped_column(String(50))
    topic_name: Mapped[Optional[str]] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

class FinalAssessment(Base):
    __tablename__ = "final_assessment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    total_questions: Mapped[int] = mapped_column(Integer)
    percentage: Mapped[float] = mapped_column(Numeric(5,2))
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class Certificate(Base):
    __tablename__ = "certificates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    certificate_id: Mapped[str] = mapped_column(String(120))
    driver_id: Mapped[str] = mapped_column(ForeignKey("drivers.id"))
    driver_name: Mapped[str] = mapped_column(String(200))
    vehicle_number: Mapped[str] = mapped_column(String(50))
    workshop_name: Mapped[Optional[str]] = mapped_column(String(255))
    final_score: Mapped[int] = mapped_column(Integer)
    final_percentage: Mapped[float] = mapped_column(Numeric(5,2))
    completion_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500))

MODULES = {"M1":"Road Safety", "M2":"Vehicle Knowledge", "M3":"Fuel & Tyres", "M4":"BS6 Technology"}
ADMIN_KEY = os.getenv("DTM_ADMIN_KEY", "")
app = FastAPI(title="Tata Motors DTM Management Reporting API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["GET"], allow_headers=["*"])

ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "dashboard" / "index.html"
# Support the flat GitHub deployment layout where index.html is at repository root.
if not DASHBOARD.exists():
    DASHBOARD = ROOT / "index.html"

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def require_admin(x_dtm_admin: Optional[str]=Header(None)):
    if not ADMIN_KEY:
        raise HTTPException(503, "DTM_ADMIN_KEY is not configured")
    if not x_dtm_admin or x_dtm_admin != ADMIN_KEY:
        raise HTTPException(401, "Admin authentication required")

def parse_date(v: Optional[str], end=False):
    if not v: return None
    try:
        dt=datetime.fromisoformat(v)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        if end and len(v)==10: dt=dt.replace(hour=23,minute=59,second=59,microsecond=999999)
        return dt
    except ValueError:
        raise HTTPException(400, f"Invalid date: {v}. Use YYYY-MM-DD or ISO datetime.")

def driver_scope(from_date=None,to_date=None,workshop_code=None,sso=None,partner_type=None):
    q=select(Driver.id).select_from(Driver).outerjoin(Workshop,Driver.workshop_id==Workshop.id)
    if from_date: q=q.where(Driver.registration_date>=from_date)
    if to_date: q=q.where(Driver.registration_date<=to_date)
    if workshop_code: q=q.where(Workshop.workshop_code==workshop_code)
    if sso: q=q.where(Workshop.sso==sso)
    if partner_type: q=q.where(Workshop.partner_type==partner_type)
    return q

def scope_params(from_date,to_date,workshop_code,sso,partner_type):
    fd=parse_date(from_date); td=parse_date(to_date,True)
    if fd and td and fd>td: raise HTTPException(400,"from_date cannot be after to_date")
    return fd,td,workshop_code,sso,partner_type

def pct(n,d): return round((float(n)/float(d))*100,1) if d else 0

def json_dt(v): return v.isoformat() if v else None

@app.get("/health")
def health():
    try:
        with SessionLocal() as s: s.execute(select(func.count()).select_from(Driver))
        return {"ok":True,"service":"DTM Management Reporting","version":"2.0.0","database":"connected"}
    except Exception as e:
        return {"ok":False,"service":"DTM Management Reporting","database":"error","detail":str(e)}

@app.get("/", include_in_schema=False)
def home(): return FileResponse(DASHBOARD)

@app.get("/dashboard", include_in_schema=False)
def dashboard(): return FileResponse(DASHBOARD)

@app.get("/api/admin/filters", dependencies=[Depends(require_admin)])
def filters(s:Session=Depends(db)):
    ssos=[x for x in s.scalars(select(Workshop.sso).where(Workshop.sso.is_not(None),Workshop.is_active==True).distinct().order_by(Workshop.sso)).all() if x]
    partners=[x for x in s.scalars(select(Workshop.partner_type).where(Workshop.partner_type.is_not(None),Workshop.is_active==True).distinct().order_by(Workshop.partner_type)).all() if x]
    cities=[x for x in s.scalars(select(Workshop.city).where(Workshop.city.is_not(None),Workshop.is_active==True).distinct().order_by(Workshop.city)).all() if x]
    return {"ssos":ssos,"partner_types":partners,"cities":cities,"modules":[{"code":k,"name":v} for k,v in MODULES.items()]}

@app.get("/api/admin/dashboard", dependencies=[Depends(require_admin)])
def dashboard_api(from_date:Optional[str]=None,to_date:Optional[str]=None,workshop_code:Optional[str]=None,sso:Optional[str]=None,partner_type:Optional[str]=None,s:Session=Depends(db)):
    fd,td,wc,ss,pt=scope_params(from_date,to_date,workshop_code,sso,partner_type)
    ids=driver_scope(fd,td,wc,ss,pt).subquery()
    total=s.scalar(select(func.count()).select_from(ids)) or 0
    started=s.scalar(select(func.count(func.distinct(ModuleProgress.driver_id))).select_from(ModuleProgress).join(ids,ModuleProgress.driver_id==ids.c.id).where(ModuleProgress.started_at.is_not(None))) or 0
    all_modules=s.scalar(select(func.count()).select_from(ModuleProgress).join(ids,ModuleProgress.driver_id==ids.c.id).where(ModuleProgress.status=="Completed").group_by(ModuleProgress.driver_id).having(func.count(func.distinct(ModuleProgress.module_code))>=4).subquery()) if False else None
    completed_ids=select(ModuleProgress.driver_id).join(ids,ModuleProgress.driver_id==ids.c.id).where(ModuleProgress.status=="Completed").group_by(ModuleProgress.driver_id).having(func.count(func.distinct(ModuleProgress.module_code))>=4).subquery()
    completed=s.scalar(select(func.count()).select_from(completed_ids)) or 0
    certified=s.scalar(select(func.count()).select_from(Driver).join(ids,Driver.id==ids.c.id).where(Driver.certificate_id.is_not(None))) or 0
    in_progress=max(total-completed,0)
    total_workshops=s.scalar(select(func.count()).select_from(Workshop).where(Workshop.is_active==True)) or 0
    active_workshops=s.scalar(select(func.count(func.distinct(Driver.workshop_id))).select_from(Driver).join(ids,Driver.id==ids.c.id).where(Driver.workshop_id.is_not(None))) or 0
    attempts=s.scalar(select(func.count()).select_from(FinalAssessment).join(ids,FinalAssessment.driver_id==ids.c.id)) or 0
    passed=s.scalar(select(func.count(func.distinct(FinalAssessment.driver_id))).select_from(FinalAssessment).join(ids,FinalAssessment.driver_id==ids.c.id).where(FinalAssessment.status.in_(["passed","Passed"]))) or 0
    return {"filters":{"from_date":from_date,"to_date":to_date,"workshop_code":wc,"sso":ss,"partner_type":pt},"kpis":{
        "registered_drivers":int(total),"training_started":int(started),"training_completed":int(completed),"in_progress":int(in_progress),"certified_drivers":int(certified),
        "certification_rate":pct(certified,total),"total_workshops":int(total_workshops),"active_workshops":int(active_workshops),"inactive_workshops":max(int(total_workshops-active_workshops),0),"workshop_adoption_rate":pct(active_workshops,total_workshops),
        "final_assessment_attempts":int(attempts),"final_passed_drivers":int(passed),"final_pass_rate":pct(passed,attempts)
    }}

@app.get("/api/admin/module-progress", dependencies=[Depends(require_admin)])
def module_progress(from_date:Optional[str]=None,to_date:Optional[str]=None,workshop_code:Optional[str]=None,sso:Optional[str]=None,partner_type:Optional[str]=None,s:Session=Depends(db)):
    fd,td,wc,ss,pt=scope_params(from_date,to_date,workshop_code,sso,partner_type); ids=driver_scope(fd,td,wc,ss,pt).subquery(); total=s.scalar(select(func.count()).select_from(ids)) or 0
    out=[]
    for code,name in MODULES.items():
        q=select(ModuleProgress).join(ids,ModuleProgress.driver_id==ids.c.id).where(ModuleProgress.module_code==code)
        rows=s.scalars(q).all(); started=sum(1 for r in rows if r.started_at); completed=sum(1 for r in rows if r.status=="Completed"); attempts=sum(int(r.pretest_attempts or 0) for r in rows); scores=[float(r.pretest_percentage or 0) for r in rows if int(r.pretest_attempts or 0)>0]
        out.append({"module_code":code,"module_name":name,"registered":int(total),"started":started,"completed":completed,"not_started":max(int(total)-started,0),"completion_rate":pct(completed,total),"start_rate":pct(started,total),"pretest_attempts":attempts,"average_pretest_percentage":round(sum(scores)/len(scores),1) if scores else 0})
    return out

@app.get("/api/admin/workshop-adoption", dependencies=[Depends(require_admin)])
def workshop_adoption(from_date:Optional[str]=None,to_date:Optional[str]=None,sso:Optional[str]=None,partner_type:Optional[str]=None,s:Session=Depends(db)):
    fd,td,_,ss,pt=scope_params(from_date,to_date,None,sso,partner_type)
    wq=select(Workshop).where(Workshop.is_active==True)
    if ss:wq=wq.where(Workshop.sso==ss)
    if pt:wq=wq.where(Workshop.partner_type==pt)
    ws=s.scalars(wq.order_by(Workshop.workshop_name)).all(); out=[]
    for w in ws:
        q=select(Driver).where(Driver.workshop_id==w.id)
        if fd:q=q.where(Driver.registration_date>=fd)
        if td:q=q.where(Driver.registration_date<=td)
        ds=s.scalars(q).all(); registered=len(ds); started=sum(1 for d in ds if d.overall_status!="Registered" or d.last_activity and d.last_activity!=d.registration_date); certified=sum(1 for d in ds if d.certificate_id); completed=0
        if ds:
            dids=[d.id for d in ds]; rows=s.execute(select(ModuleProgress.driver_id,func.count(func.distinct(ModuleProgress.module_code))).where(ModuleProgress.driver_id.in_(dids),ModuleProgress.status=="Completed").group_by(ModuleProgress.driver_id)).all(); completed=sum(1 for _,n in rows if n>=4)
        out.append({"workshop_code":w.workshop_code,"workshop_name":w.workshop_name,"city":w.city,"sso":w.sso,"region":w.region,"partner_type":w.partner_type,"registered":registered,"started":started,"completed":completed,"certified":certified,"adoption_status":"Active" if registered else "Not Started","adoption_percent":100 if registered else 0})
    return out

@app.get("/api/admin/certifications", dependencies=[Depends(require_admin)])
def certifications(from_date:Optional[str]=None,to_date:Optional[str]=None,workshop_code:Optional[str]=None,sso:Optional[str]=None,partner_type:Optional[str]=None,limit:int=Query(500,ge=1,le=5000),s:Session=Depends(db)):
    fd,td,wc,ss,pt=scope_params(from_date,to_date,workshop_code,sso,partner_type)
    q=select(Certificate,Driver,Workshop).join(Driver,Certificate.driver_id==Driver.id).outerjoin(Workshop,Driver.workshop_id==Workshop.id)
    if fd:q=q.where(Certificate.completion_date>=fd)
    if td:q=q.where(Certificate.completion_date<=td)
    if wc:q=q.where(Workshop.workshop_code==wc)
    if ss:q=q.where(Workshop.sso==ss)
    if pt:q=q.where(Workshop.partner_type==pt)
    rows=s.execute(q.order_by(Certificate.completion_date.desc()).limit(limit)).all()
    return [{"certificate_id":c.certificate_id,"driver_id":d.driver_id,"driver_name":c.driver_name,"mobile_number":d.mobile_number,"vehicle_number":c.vehicle_number,"vehicle_model":d.vehicle_model,"workshop_name":c.workshop_name,"sso":w.sso if w else None,"final_score":c.final_score,"final_percentage":float(c.final_percentage or 0),"completion_date":json_dt(c.completion_date),"certificate_url":c.certificate_url} for c,d,w in rows]

@app.get("/api/admin/drivers-report", dependencies=[Depends(require_admin)])
def drivers_report(from_date:Optional[str]=None,to_date:Optional[str]=None,workshop_code:Optional[str]=None,sso:Optional[str]=None,partner_type:Optional[str]=None,search:Optional[str]=None,limit:int=Query(500,ge=1,le=5000),s:Session=Depends(db)):
    fd,td,wc,ss,pt=scope_params(from_date,to_date,workshop_code,sso,partner_type)
    q=select(Driver,Workshop).outerjoin(Workshop,Driver.workshop_id==Workshop.id)
    if fd:q=q.where(Driver.registration_date>=fd)
    if td:q=q.where(Driver.registration_date<=td)
    if wc:q=q.where(Workshop.workshop_code==wc)
    if ss:q=q.where(Workshop.sso==ss)
    if pt:q=q.where(Workshop.partner_type==pt)
    if search:
        like=f"%{search.strip()}%"; q=q.where(or_(Driver.full_name.ilike(like),Driver.mobile_number.ilike(like),Driver.vehicle_number.ilike(like),Driver.driver_id.ilike(like),Driver.licence_number.ilike(like)))
    rows=s.execute(q.order_by(Driver.registration_date.desc()).limit(limit)).all(); out=[]
    for d,w in rows:
        mods=s.scalars(select(ModuleProgress).where(ModuleProgress.driver_id==d.id)).all(); md={m.module_code:{"status":m.status,"pretest_percentage":float(m.pretest_percentage or 0),"completed_at":json_dt(m.completed_at)} for m in mods}
        finals=s.scalars(select(FinalAssessment).where(FinalAssessment.driver_id==d.id).order_by(FinalAssessment.attempt_number.desc()).limit(1)).first()
        out.append({"driver_id":d.driver_id,"full_name":d.full_name,"mobile_number":d.mobile_number,"licence_number":d.licence_number,"vehicle_number":d.vehicle_number,"vehicle_model":d.vehicle_model,"workshop_name":d.workshop_name,"sso":w.sso if w else None,"partner_type":w.partner_type if w else None,"status":d.overall_status,"completion_percentage":float(d.completion_percentage or 0),"registration_date":json_dt(d.registration_date),"last_activity":json_dt(d.last_activity),"certificate_id":d.certificate_id,"final_score":finals.score if finals else None,"final_percentage":float(finals.percentage) if finals else None,"final_status":finals.status if finals else None,"modules":md})
    return out

@app.get("/api/admin/daily-trend", dependencies=[Depends(require_admin)])
def daily_trend(days:int=Query(30,ge=1,le=365),s:Session=Depends(db)):
    today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0); out=[]
    for i in range(days-1,-1,-1):
        start=today-timedelta(days=i); end=start+timedelta(days=1)
        reg=s.scalar(select(func.count()).select_from(Driver).where(Driver.registration_date>=start,Driver.registration_date<end)) or 0
        cert=s.scalar(select(func.count()).select_from(Certificate).where(Certificate.completion_date>=start,Certificate.completion_date<end)) or 0
        ass=s.scalar(select(func.count()).select_from(FinalAssessment).where(FinalAssessment.completed_at>=start,FinalAssessment.completed_at<end)) or 0
        mods=s.scalar(select(func.count()).select_from(ModuleProgress).where(ModuleProgress.completed_at>=start,ModuleProgress.completed_at<end)) or 0
        out.append({"date":start.date().isoformat(),"registered":int(reg),"certified":int(cert),"assessments":int(ass),"module_completions":int(mods)})
    return out

@app.get("/api/admin/export/drivers.csv", dependencies=[Depends(require_admin)])
def export_drivers(from_date:Optional[str]=None,to_date:Optional[str]=None,workshop_code:Optional[str]=None,sso:Optional[str]=None,partner_type:Optional[str]=None,s:Session=Depends(db)):
    data=drivers_report(from_date,to_date,workshop_code,sso,partner_type,None,5000,s)
    lines=["Driver ID,Name,Mobile,Licence,Vehicle,Model,Workshop,SSO,Partner,Status,Completion %,Certificate,Final %"]
    for x in data:
        vals=[x["driver_id"],x["full_name"],x["mobile_number"],x["licence_number"],x["vehicle_number"],x["vehicle_model"],x["workshop_name"],x["sso"],x["partner_type"],x["status"],x["completion_percentage"],x["certificate_id"] or "",x["final_percentage"] if x["final_percentage"] is not None else ""]
        lines.append(",".join('"'+str(v or '').replace('"','""')+'"' for v in vals))
    return StreamingResponse(iter(["\n".join(lines)]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=DTM_Driver_MIS.csv"})
