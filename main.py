import os, uuid, csv, hashlib, secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Boolean, DateTime, Integer, Numeric, ForeignKey, UniqueConstraint, select, func, case, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, relationship, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./dtm.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://','postgresql+psycopg://',1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://','postgresql+psycopg://',1)

connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

class Workshop(Base):
    __tablename__='workshops'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    customer_code: Mapped[Optional[str]] = mapped_column(String(100))
    workshop_code: Mapped[str] = mapped_column(String(100), index=True)
    workshop_name: Mapped[str] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(80), default='Rajasthan')
    sso: Mapped[Optional[str]] = mapped_column(String(120))
    region: Mapped[Optional[str]] = mapped_column(String(120))
    workshop_division: Mapped[Optional[str]] = mapped_column(String(120))
    partner_type: Mapped[Optional[str]] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class Driver(Base):
    __tablename__='drivers'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    driver_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    mobile_number: Mapped[str] = mapped_column(String(20), index=True)
    licence_number: Mapped[str] = mapped_column(String(100), index=True)
    vehicle_number: Mapped[str] = mapped_column(String(50))
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(150))
    workshop_id: Mapped[Optional[str]] = mapped_column(ForeignKey('workshops.id'))
    workshop_name: Mapped[Optional[str]] = mapped_column(String(255))
    dealer_name: Mapped[Optional[str]] = mapped_column(String(255))
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    overall_status: Mapped[str] = mapped_column(String(50), default='Registered')
    completion_percentage: Mapped[float] = mapped_column(Numeric(5,2), default=0)
    completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    certificate_id: Mapped[Optional[str]] = mapped_column(String(120))

class ModuleProgress(Base):
    __tablename__='module_progress'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    driver_id: Mapped[str] = mapped_column(ForeignKey('drivers.id', ondelete='CASCADE'), index=True)
    module_code: Mapped[str] = mapped_column(String(20))
    module_name: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default='Not Started')
    pretest_score: Mapped[int] = mapped_column(Integer, default=0)
    pretest_total: Mapped[int] = mapped_column(Integer, default=5)
    pretest_percentage: Mapped[float] = mapped_column(Numeric(5,2), default=0)
    pretest_attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    __table_args__=(UniqueConstraint('driver_id','module_code',name='uq_driver_module'),)

class TrainingSession(Base):
    __tablename__='training_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    driver_id: Mapped[str] = mapped_column(ForeignKey('drivers.id'), index=True)
    module_code: Mapped[str] = mapped_column(String(20))
    topic_code: Mapped[Optional[str]] = mapped_column(String(50))
    topic_name: Mapped[Optional[str]] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class FinalAssessment(Base):
    __tablename__='final_assessment'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    driver_id: Mapped[str] = mapped_column(ForeignKey('drivers.id'), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=20)
    percentage: Mapped[float] = mapped_column(Numeric(5,2), default=0)
    status: Mapped[str] = mapped_column(String(30), default='Failed')
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class Certificate(Base):
    __tablename__='certificates'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    certificate_id: Mapped[str] = mapped_column(String(120), unique=True)
    driver_id: Mapped[str] = mapped_column(ForeignKey('drivers.id'), index=True)
    driver_name: Mapped[str] = mapped_column(String(200))
    vehicle_number: Mapped[str] = mapped_column(String(50))
    workshop_name: Mapped[Optional[str]] = mapped_column(String(255))
    final_score: Mapped[int] = mapped_column(Integer)
    final_percentage: Mapped[float] = mapped_column(Numeric(5,2))
    completion_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

# Production PostgreSQL schema is managed separately; do not mutate it from the web app.
if DATABASE_URL.startswith('sqlite'):
    Base.metadata.create_all(engine)

APP_KEY=os.getenv('DTM_APP_KEY','')
ADMIN_KEY=os.getenv('DTM_ADMIN_KEY','')

ROOT=Path(__file__).resolve().parent
INDEX_HTML=ROOT/'index.html'
app=FastAPI(title='Tata Motors DTM Driver Training', version='V40.2-PG')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['*'], allow_headers=['*'])

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def require_app_key(x_dtm_key: Optional[str]=Header(None)):
    if APP_KEY and not secrets.compare_digest(x_dtm_key or '', APP_KEY):
        raise HTTPException(401,'Invalid DTM application key')

def require_admin(x_dtm_admin: Optional[str]=Header(None)):
    if not ADMIN_KEY or not secrets.compare_digest(x_dtm_admin or '', ADMIN_KEY):
        raise HTTPException(401,'Admin authentication required')

class Registration(BaseModel):
    full_name:str=Field(min_length=2,max_length=200)
    mobile_number:str=Field(pattern=r'^\d{10}$')
    licence_number:str=Field(min_length=2,max_length=100)
    vehicle_number:str=Field(min_length=2,max_length=50)
    vehicle_model:str=Field(min_length=1,max_length=150)
    workshop_code:str=Field(min_length=1,max_length=100)
    workshop_name:Optional[str]=None

class DriverPatch(BaseModel):
    last_activity:Optional[datetime]=None
    completion_percentage:Optional[float]=None
    overall_status:Optional[str]=None
    completion_date:Optional[datetime]=None
    certificate_id:Optional[str]=None

class ModuleResult(BaseModel):
    score:int=Field(ge=0,le=5)
    total:int=Field(default=5,ge=1,le=5)
    percentage:float=Field(ge=0,le=100)

class FinalResult(BaseModel):
    score:int=Field(ge=0,le=20)
    total:int=Field(default=20,ge=1,le=20)
    percentage:float=Field(ge=0,le=100)
    started_at:Optional[datetime]=None
    completed_at:Optional[datetime]=None

class TopicStart(BaseModel):
    module_code:str
    topic_code:Optional[str]=None
    topic_name:Optional[str]=None
    started_at:Optional[datetime]=None

class CertificateIn(BaseModel):
    certificate_id:str
    driver_name:str
    vehicle_number:str
    workshop_name:Optional[str]=None
    final_score:int
    final_percentage:float
    completion_date:Optional[datetime]=None

@app.get('/health')
def health():
    return {'ok':True,'service':'Tata Motors DTM Driver Training','version':'V40.2-PG','database_configured':bool(os.getenv('DATABASE_URL'))}

@app.get('/')
def home():
    if not INDEX_HTML.exists(): raise HTTPException(500, 'index.html is missing from deployment')
    return FileResponse(INDEX_HTML, media_type='text/html')

@app.get('/api/workshops')
def workshops(s:Session=Depends(db)):
    rows=s.scalars(select(Workshop).where(Workshop.is_active==True).order_by(Workshop.workshop_name,Workshop.city)).all()
    return [{'id':r.id,'workshop_code':r.workshop_code,'workshop_name':r.workshop_name,'city':r.city,'sso':r.sso,'region':r.region,'workshop_division':r.workshop_division,'partner_type':r.partner_type} for r in rows]

@app.post('/api/drivers/register')
def register(x:Registration,s:Session=Depends(db)):
    w=s.scalar(select(Workshop).where(Workshop.workshop_code==x.workshop_code,Workshop.is_active==True))
    if not w: raise HTTPException(400,'Workshop not found or inactive')
    # Prevent accidental duplicate registration from a retry; mobile + licence + vehicle is the natural registration fingerprint.
    existing=s.scalar(select(Driver).where(Driver.mobile_number==x.mobile_number,Driver.licence_number==x.licence_number,Driver.vehicle_number==x.vehicle_number))
    if existing:
        return {'success':True,'existing':True,'driver_id':existing.id,'driver_code':existing.driver_id}
    did=str(uuid.uuid4()); code='TM-DT-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(3).upper()
    d=Driver(id=did,driver_id=code,full_name=x.full_name.strip(),mobile_number=x.mobile_number,licence_number=x.licence_number.strip(),vehicle_number=x.vehicle_number.strip().upper(),vehicle_model=x.vehicle_model.strip(),workshop_id=w.id,workshop_name=w.workshop_name,dealer_name=w.workshop_name)
    s.add(d)
    for i in range(1,5): s.add(ModuleProgress(driver_id=did,module_code=f'M{i}',module_name=f'Module {i}',status='Not Started'))
    s.commit()
    return {'success':True,'existing':False,'driver_id':did,'driver_code':code}

@app.patch('/api/drivers/{driver_id}')
def patch_driver(driver_id:str,x:DriverPatch,s:Session=Depends(db)):
    d=s.get(Driver,driver_id)
    if not d: raise HTTPException(404,'Driver not found')
    for k,v in x.model_dump(exclude_none=True).items(): setattr(d,k,v)
    d.last_activity=datetime.now(timezone.utc); s.commit(); return {'success':True}

@app.post('/api/drivers/{driver_id}/topics')
def topic(driver_id:str,x:TopicStart,s:Session=Depends(db)):
    if not s.get(Driver,driver_id): raise HTTPException(404,'Driver not found')
    s.add(TrainingSession(driver_id=driver_id,module_code=x.module_code,topic_code=x.topic_code,topic_name=x.topic_name,started_at=x.started_at or datetime.now(timezone.utc)))
    s.commit(); return {'success':True}

@app.post('/api/drivers/{driver_id}/modules/{module_code}/pretest')
def pretest(driver_id:str,module_code:str,x:ModuleResult,s:Session=Depends(db)):
    row=s.scalar(select(ModuleProgress).where(ModuleProgress.driver_id==driver_id,ModuleProgress.module_code==module_code))
    if not row: raise HTTPException(404,'Module progress not found')
    row.started_at = row.started_at or datetime.now(timezone.utc); row.status='Completed'; row.pretest_score=x.score; row.pretest_total=x.total; row.pretest_percentage=x.percentage; row.pretest_attempts+=1; row.completed_at=datetime.now(timezone.utc); row.last_activity=datetime.now(timezone.utc); row.updated_at=datetime.now(timezone.utc)
    s.flush()
    completed=s.query(ModuleProgress).filter(ModuleProgress.driver_id==driver_id,ModuleProgress.status=='Completed').count()
    d=s.get(Driver,driver_id); d.completion_percentage=min(80,completed*20); d.overall_status='Modules Completed' if completed==4 else 'In Training'; d.last_activity=datetime.now(timezone.utc)
    s.commit(); return {'success':True,'completed_modules':completed}

@app.post('/api/drivers/{driver_id}/final')
def final(driver_id:str,x:FinalResult,s:Session=Depends(db)):
    if not s.get(Driver,driver_id): raise HTTPException(404,'Driver not found')
    last=s.scalar(select(FinalAssessment).where(FinalAssessment.driver_id==driver_id).order_by(FinalAssessment.attempt_number.desc()))
    attempt=(last.attempt_number+1) if last else 1
    passed=x.percentage>=70
    s.add(FinalAssessment(driver_id=driver_id,attempt_number=attempt,score=x.score,total_questions=x.total,percentage=x.percentage,status='passed' if passed else 'failed',started_at=x.started_at,completed_at=x.completed_at or datetime.now(timezone.utc)))
    d=s.get(Driver,driver_id); d.completion_percentage=100 if passed else 80; d.overall_status='Completed' if passed else 'Final Assessment'; d.last_activity=datetime.now(timezone.utc)
    s.commit(); return {'success':True,'attempt_number':attempt,'passed':passed}

@app.post('/api/drivers/{driver_id}/certificate')
def certificate(driver_id:str,x:CertificateIn,s:Session=Depends(db)):
    if x.final_percentage<70: raise HTTPException(400,'Certificate requires a passing final assessment')
    existing=s.scalar(select(Certificate).where(Certificate.certificate_id==x.certificate_id))
    if existing: return {'success':True,'existing':True}
    s.add(Certificate(certificate_id=x.certificate_id,driver_id=driver_id,driver_name=x.driver_name,vehicle_number=x.vehicle_number,workshop_name=x.workshop_name,final_score=x.final_score,final_percentage=x.final_percentage,completion_date=x.completion_date or datetime.now(timezone.utc)))
    d=s.get(Driver,driver_id); d.certificate_id=x.certificate_id; d.completion_date=x.completion_date or datetime.now(timezone.utc); d.completion_percentage=100; d.overall_status='Completed'; s.commit(); return {'success':True}

@app.get('/api/admin/drivers', dependencies=[Depends(require_admin)])
def admin_drivers(s:Session=Depends(db)):
    rows=s.scalars(select(Driver).order_by(Driver.registration_date.desc())).all()
    return [{'id':d.id,'driver_id':d.driver_id,'full_name':d.full_name,'mobile_number':d.mobile_number,'licence_number':d.licence_number,'vehicle_number':d.vehicle_number,'vehicle_model':d.vehicle_model,'workshop_name':d.workshop_name,'status':d.overall_status,'completion_percentage':float(d.completion_percentage or 0),'registration_date':d.registration_date.isoformat() if d.registration_date else None} for d in rows]

def seed_workshops():
    s=SessionLocal()
    try:
        if s.scalar(select(Workshop.id).limit(1)): return
        path=Path(__file__).resolve().parent/'workshops.csv'
        if not path.exists(): return
        with path.open(newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                code=(r.get('workshop_code') or r.get('Customer Code') or '').strip()
                name=(r.get('workshop_name') or r.get('Workshop Name') or '').strip()
                if not code or not name: continue
                s.add(Workshop(customer_code=r.get('customer_code') or r.get('Customer Code'),workshop_code=code,workshop_name=name,city=r.get('city') or r.get('Workshop City'),state='Rajasthan',sso=r.get('sso') or r.get('SSO'),region=r.get('region') or r.get('Region'),workshop_division=r.get('workshop_division') or r.get('WORKSHOP Division'),partner_type=r.get('partner_type') or r.get('Partner TYPE ( DEALER /TASS)')))
        s.commit()
    finally: s.close()


# ---------------- MANAGEMENT REPORTING APIs ----------------
MODULES = {
    'M1': 'Road Safety',
    'M2': 'Vehicle Knowledge',
    'M3': 'Fuel & Tyres',
    'M4': 'BS6 Technology',
}

def _parse_date(v: Optional[str], end=False):
    if not v:
        return None
    try:
        # Date-only filters are interpreted in UTC for consistent reporting.
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(400, f'Invalid date: {v}. Use ISO format.')

def _date_filters(start: Optional[str], end: Optional[str]):
    sd, ed = _parse_date(start), _parse_date(end, True)
    if ed and len(end or '') == 10:
        # Inclusive end date when supplied as YYYY-MM-DD.
        ed = ed.replace(hour=23, minute=59, second=59, microsecond=999999)
    if sd and ed and sd > ed:
        raise HTTPException(400, 'from_date cannot be after to_date')
    return sd, ed

def _driver_query(s: Session, from_date=None, to_date=None, workshop_code=None, sso=None, partner_type=None):
    q = select(Driver, Workshop).outerjoin(Workshop, Driver.workshop_id == Workshop.id)
    if from_date:
        q = q.where(Driver.registration_date >= from_date)
    if to_date:
        q = q.where(Driver.registration_date <= to_date)
    if workshop_code:
        q = q.where(Workshop.workshop_code == workshop_code)
    if sso:
        q = q.where(Workshop.sso == sso)
    if partner_type:
        q = q.where(Workshop.partner_type == partner_type)
    return q

@app.get('/api/admin/dashboard', dependencies=[Depends(require_admin)])
def admin_dashboard(
    from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    workshop_code: Optional[str] = Query(None), sso: Optional[str] = Query(None),
    partner_type: Optional[str] = Query(None), s: Session = Depends(db)):
    sd, ed = _date_filters(from_date, to_date)
    dq = _driver_query(s, sd, ed, workshop_code, sso, partner_type).subquery()
    total = s.scalar(select(func.count()).select_from(dq)) or 0
    certified = s.scalar(select(func.count()).select_from(dq).where(dq.c.certificate_id.is_not(None))) or 0
    started = s.scalar(select(func.count()).select_from(dq).where(dq.c.overall_status != 'Registered')) or 0

    # A driver is module-complete only when all four module progress rows are Completed,
    # regardless of whether the driver later passed or failed the final assessment.
    module_complete_ids = (
        select(ModuleProgress.driver_id)
        .where(ModuleProgress.module_code.in_(list(MODULES.keys())), ModuleProgress.status == 'Completed')
        .group_by(ModuleProgress.driver_id)
        .having(func.count(func.distinct(ModuleProgress.module_code)) == len(MODULES))
        .subquery()
    )
    modules_completed = s.scalar(
        select(func.count()).select_from(dq).where(dq.c.id.in_(select(module_complete_ids.c.driver_id)))
    ) or 0
    # In-progress means registered but not certified and not yet fully module-complete.
    in_progress = max(total - certified, 0)
    active_workshops = s.scalar(select(func.count(func.distinct(dq.c.workshop_id))).select_from(dq).where(dq.c.workshop_id.is_not(None))) or 0
    total_workshops = s.scalar(select(func.count()).select_from(Workshop).where(Workshop.is_active == True)) or 0
    passed = s.scalar(select(func.count(func.distinct(FinalAssessment.driver_id))).select_from(FinalAssessment).join(dq, FinalAssessment.driver_id == dq.c.id).where(FinalAssessment.status == 'passed')) or 0
    failed = s.scalar(select(func.count(func.distinct(FinalAssessment.driver_id))).select_from(FinalAssessment).join(dq, FinalAssessment.driver_id == dq.c.id).where(FinalAssessment.status == 'failed')) or 0
    return {
        'filters': {'from_date': from_date, 'to_date': to_date, 'workshop_code': workshop_code, 'sso': sso, 'partner_type': partner_type},
        'kpis': {
            'registered_drivers': total, 'training_started': started, 'in_progress': in_progress,
            'modules_completed': modules_completed, 'certified_drivers': certified,
            'certification_rate': round((certified / total * 100), 1) if total else 0,
            'active_workshops': active_workshops, 'total_workshops': total_workshops,
            'workshop_adoption_rate': round((active_workshops / total_workshops * 100), 1) if total_workshops else 0,
            'final_passed_drivers': passed, 'final_failed_drivers': failed,
        }
    }

@app.get('/api/admin/workshop-adoption', dependencies=[Depends(require_admin)])
def admin_workshop_adoption(
    from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    sso: Optional[str] = Query(None), partner_type: Optional[str] = Query(None),
    s: Session = Depends(db)):
    sd, ed = _date_filters(from_date, to_date)
    q = select(Workshop).where(Workshop.is_active == True)
    if sso: q = q.where(Workshop.sso == sso)
    if partner_type: q = q.where(Workshop.partner_type == partner_type)
    workshops = s.scalars(q.order_by(Workshop.workshop_name)).all()
    module_complete_ids = (select(ModuleProgress.driver_id).where(ModuleProgress.module_code.in_(list(MODULES.keys())), ModuleProgress.status == 'Completed').group_by(ModuleProgress.driver_id).having(func.count(func.distinct(ModuleProgress.module_code)) == len(MODULES)).subquery())
    out=[]
    for w in workshops:
        dq = select(Driver).where(Driver.workshop_id == w.id)
        if sd: dq=dq.where(Driver.registration_date>=sd)
        if ed: dq=dq.where(Driver.registration_date<=ed)
        registered=s.scalar(select(func.count()).select_from(dq.subquery())) or 0
        certified=s.scalar(select(func.count()).select_from(dq.where(Driver.certificate_id.is_not(None)).subquery())) or 0
        completed=s.scalar(select(func.count()).select_from(dq.where(Driver.id.in_(select(module_complete_ids.c.driver_id))).subquery())) or 0
        started=s.scalar(select(func.count()).select_from(dq.where(Driver.overall_status!='Registered').subquery())) or 0
        out.append({'workshop_code':w.workshop_code,'workshop_name':w.workshop_name,'city':w.city,'sso':w.sso,'region':w.region,'partner_type':w.partner_type,'registered':registered,'started':started,'completed':completed,'certified':certified,'adoption_status':'Active' if registered else 'Not Started'})
    return out

@app.get('/api/admin/module-progress', dependencies=[Depends(require_admin)])
def admin_module_progress(
    from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    workshop_code: Optional[str] = Query(None), sso: Optional[str] = Query(None),
    partner_type: Optional[str] = Query(None), s: Session = Depends(db)):
    sd, ed = _date_filters(from_date, to_date)
    dq = _driver_query(s, sd, ed, workshop_code, sso, partner_type).subquery()
    total = s.scalar(select(func.count()).select_from(dq)) or 0
    out=[]
    for code,name in MODULES.items():
        mp = select(ModuleProgress).join(dq, ModuleProgress.driver_id == dq.c.id).where(ModuleProgress.module_code == code).subquery()
        started=s.scalar(select(func.count()).select_from(mp).where(mp.c.started_at.is_not(None))) or 0
        completed=s.scalar(select(func.count()).select_from(mp).where(mp.c.status=='Completed')) or 0
        attempts=s.scalar(select(func.sum(mp.c.pretest_attempts)).select_from(mp)) or 0
        avg=s.scalar(select(func.avg(mp.c.pretest_percentage)).select_from(mp).where(mp.c.pretest_attempts>0))
        out.append({'module_code':code,'module_name':name,'registered':total,'started':started,'completed':completed,'completion_rate':round(completed/total*100,1) if total else 0,'pretest_attempts':int(attempts or 0),'average_pretest_percentage':round(float(avg or 0),1)})
    return out

@app.get('/api/admin/certifications', dependencies=[Depends(require_admin)])
def admin_certifications(
    from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    workshop_code: Optional[str] = Query(None), sso: Optional[str] = Query(None),
    partner_type: Optional[str] = Query(None), s: Session = Depends(db)):
    sd, ed = _date_filters(from_date, to_date)
    q = select(Certificate, Driver, Workshop).join(Driver, Certificate.driver_id==Driver.id).outerjoin(Workshop, Driver.workshop_id==Workshop.id)
    if sd: q=q.where(Certificate.completion_date>=sd)
    if ed: q=q.where(Certificate.completion_date<=ed)
    if workshop_code: q=q.where(Workshop.workshop_code==workshop_code)
    if sso: q=q.where(Workshop.sso==sso)
    if partner_type: q=q.where(Workshop.partner_type==partner_type)
    rows=s.execute(q.order_by(Certificate.completion_date.desc())).all()
    return [{'certificate_id':c.certificate_id,'driver_id':d.driver_id,'driver_name':c.driver_name,'vehicle_number':c.vehicle_number,'workshop_name':c.workshop_name,'final_score':c.final_score,'final_percentage':float(c.final_percentage),'completion_date':c.completion_date.isoformat() if c.completion_date else None} for c,d,w in rows]

@app.get('/api/admin/daily-trend', dependencies=[Depends(require_admin)])
def admin_daily_trend(
    days: int = Query(30, ge=1, le=365), from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    workshop_code: Optional[str] = Query(None), sso: Optional[str] = Query(None), partner_type: Optional[str] = Query(None),
    s: Session = Depends(db)):
    sd, ed = _date_filters(from_date, to_date)
    # Trend is always returned for the requested rolling period; management filters are applied to driver-based metrics.
    cutoff = datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    if sd:
        cutoff = sd.replace(hour=0, minute=0, second=0, microsecond=0)
    out=[]
    for i in range(days-1,-1,-1):
        start=cutoff - __import__('datetime').timedelta(days=i)
        end=start + __import__('datetime').timedelta(days=1)
        if ed and start > ed:
            out.append({'date':start.date().isoformat(),'registered':0,'certified':0,'assessments':0})
            continue
        dq = _driver_query(s, None, None, workshop_code, sso, partner_type).subquery()
        reg=s.scalar(select(func.count()).select_from(dq).where(dq.c.registration_date>=start,dq.c.registration_date<end)) or 0
        cert=s.scalar(select(func.count()).select_from(Certificate).join(dq, Certificate.driver_id==dq.c.id).where(Certificate.completion_date>=start,Certificate.completion_date<end)) or 0
        fin=s.scalar(select(func.count()).select_from(FinalAssessment).join(dq, FinalAssessment.driver_id==dq.c.id).where(FinalAssessment.completed_at>=start,FinalAssessment.completed_at<end)) or 0
        out.append({'date':start.date().isoformat(),'registered':reg,'certified':cert,'assessments':fin})
    return out

@app.get('/api/admin/drivers-report', dependencies=[Depends(require_admin)])
def admin_drivers_report(
    from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    workshop_code: Optional[str] = Query(None), sso: Optional[str] = Query(None),
    partner_type: Optional[str] = Query(None), search: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000), s: Session = Depends(db)):
    sd, ed = _date_filters(from_date, to_date)
    q=_driver_query(s,sd,ed,workshop_code,sso,partner_type)
    if search:
        like=f'%{search.strip()}%'
        q=q.where(or_(Driver.full_name.ilike(like),Driver.mobile_number.ilike(like),Driver.vehicle_number.ilike(like),Driver.driver_id.ilike(like),Driver.licence_number.ilike(like)))
    rows=s.execute(q.order_by(Driver.registration_date.desc()).limit(limit)).all()
    result=[]
    for d,w in rows:
        mods=s.scalars(select(ModuleProgress).where(ModuleProgress.driver_id==d.id)).all()
        mod={m.module_code:{'status':m.status,'pretest_percentage':float(m.pretest_percentage or 0)} for m in mods}
        last_final=s.scalar(select(FinalAssessment).where(FinalAssessment.driver_id==d.id).order_by(FinalAssessment.attempt_number.desc()))
        result.append({'driver_id':d.driver_id,'full_name':d.full_name,'mobile_number':d.mobile_number,'licence_number':d.licence_number,'vehicle_number':d.vehicle_number,'vehicle_model':d.vehicle_model,'workshop_name':d.workshop_name,'sso':w.sso if w else None,'partner_type':w.partner_type if w else None,'status':d.overall_status,'completion_percentage':float(d.completion_percentage or 0),'registration_date':d.registration_date.isoformat() if d.registration_date else None,'certificate_id':d.certificate_id,'final_score':last_final.score if last_final else None,'final_percentage':float(last_final.percentage) if last_final else None,'final_status':last_final.status if last_final else None,'modules':mod})
    return result

@app.get('/api/admin/filters', dependencies=[Depends(require_admin)])
def admin_filters(s:Session=Depends(db)):
    ssos=[x for x in s.scalars(select(Workshop.sso).where(Workshop.sso.is_not(None)).distinct().order_by(Workshop.sso)).all() if x]
    partners=[x for x in s.scalars(select(Workshop.partner_type).where(Workshop.partner_type.is_not(None)).distinct().order_by(Workshop.partner_type)).all() if x]
    workshops=[{'workshop_code':w.workshop_code,'workshop_name':w.workshop_name,'city':w.city} for w in s.scalars(select(Workshop).where(Workshop.is_active==True).order_by(Workshop.workshop_name)).all()]
    return {'ssos':ssos,'partner_types':partners,'workshops':workshops}

seed_workshops()
