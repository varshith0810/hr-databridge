"""
api/main.py
FastAPI application entrypoint.

Endpoints:
  GET  /health                    — DB + service health check
  POST /sync/trigger              — Manually trigger a sync cycle
  GET  /sync/status               — Latest sync summary per source
  GET  /sync/logs                 — Paginated audit log
  GET  /analytics/headcount       — Headcount by department
  GET  /analytics/attrition       — Monthly attrition rates
  GET  /analytics/diversity       — Diversity breakdown
  GET  /analytics/tenure          — Average tenure by department
  GET  /analytics/data-quality    — Data completeness per source
"""

import logging
import os
import time
import threading
from datetime import date
from typing import Optional
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from storage.db import init_db, get_session, health_check
from storage.models import SyncLog, KPISnapshot, Employee
from sqlalchemy import text, desc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HR DataBridge API",
    description="ATS Integration Middleware + Workforce Analytics Platform",
    version="1.0.0",
    docs_url="/docs",
)

ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:3000",   # CRA fallback
    "https://hr-databridge-frontend.onrender.com",  # Render production
    os.getenv("FRONTEND_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("HR DataBridge API started.")


# --------------------------------------------------------------------------- #
#  Response models
# --------------------------------------------------------------------------- #

class SyncStatusResponse(BaseModel):
    source_system: str
    last_synced_at: Optional[str]
    records_pulled: int
    records_inserted: int
    records_updated: int
    conflicts_detected: int
    status: str
    duration_seconds: Optional[float]


class KPIResponse(BaseModel):
    kpi_name: str
    dimension: str
    value: float
    unit: Optional[str]
    snapshot_date: str


class TriggerResponse(BaseModel):
    message: str
    triggered_at: str


# --------------------------------------------------------------------------- #
#  Health
# --------------------------------------------------------------------------- #

@app.get("/health", tags=["ops"])
def health():
    db_status = health_check()
    return {
        "service": "hr-databridge",
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "database": db_status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# --------------------------------------------------------------------------- #
#  Sync endpoints
# --------------------------------------------------------------------------- #

_sync_running = False   # Simple in-process guard against concurrent manual triggers

def _run_sync_background():
    """Runs Greenhouse + Workday sync + KPI in a background thread."""
    global _sync_running
    _sync_running = True
    try:
        from ingestion.api_poller import GreenhousePoller, WorkdayPoller
        from ingestion.payload_parser import GreenhouseParser, WorkdayParser
        from ingestion.schema_normalizer import SchemaNormalizer
        from ingestion.delta_tracker import DeltaTracker
        from analytics.kpi_engine import KPIEngine
        from storage.models import Employee

        for source, poller_cls, parser_cls in [
            ("greenhouse", GreenhousePoller, GreenhouseParser),
            ("workday", WorkdayPoller, WorkdayParser),
        ]:
            start = time.time()
            poller = poller_cls()
            stats = dict(pulled=0, inserted=0, updated=0, skipped=0)
            try:
                with get_session() as session:
                    tracker = DeltaTracker(session)
                    cursor = tracker.get_last_cursor(source)
                    next_cursor = poller.get_next_cursor()
                    fetch_fn = poller.fetch_since(cursor=cursor)

                    for raw in fetch_fn:
                        stats["pulled"] += 1
                        try:
                            parsed = parser_cls.parse(raw)
                            emp = SchemaNormalizer.normalize(parsed)
                            existing = session.query(Employee).filter_by(
                                employee_id=emp.employee_id, source_system=source
                            ).first()
                            if existing:
                                for f in ["full_name", "email", "department", "job_title", "status"]:
                                    setattr(existing, f, getattr(emp, f))
                                stats["updated"] += 1
                            else:
                                session.add(emp)
                                stats["inserted"] += 1
                        except Exception:
                            stats["skipped"] += 1

                    tracker.write_sync_log(
                        source_system=source, cursor_used=cursor, cursor_next=next_cursor,
                        records_pulled=stats["pulled"], records_inserted=stats["inserted"],
                        records_updated=stats["updated"], records_skipped=stats["skipped"],
                        conflicts_detected=0, conflicts_resolved=0,
                        duration_seconds=time.time() - start, status="success"
                    )
            finally:
                poller.close()

        with get_session() as session:
            KPIEngine(session).run_all()

        logger.info("Manual sync completed successfully.")
    except Exception as exc:
        logger.error(f"Manual sync failed: {exc}")
    finally:
        _sync_running = False


@app.post("/sync/trigger", response_model=TriggerResponse, tags=["sync"])
def trigger_sync(background_tasks: BackgroundTasks):
    """Manually trigger a full sync cycle (runs in background)."""
    if _sync_running:
        raise HTTPException(status_code=409, detail="A sync is already in progress.")
    background_tasks.add_task(_run_sync_background)
    return TriggerResponse(
        message="Sync triggered. Check /sync/status for progress.",
        triggered_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


@app.get("/sync/status", response_model=list[SyncStatusResponse], tags=["sync"])
def sync_status():
    """Returns the latest sync log entry for each source system."""
    with get_session() as session:
        results = []
        for source in ("greenhouse", "workday"):
            log = (
                session.query(SyncLog)
                .filter(SyncLog.source_system == source)
                .order_by(desc(SyncLog.synced_at))
                .first()
            )
            if log:
                results.append(SyncStatusResponse(
                    source_system=log.source_system,
                    last_synced_at=log.synced_at.isoformat(),
                    records_pulled=log.records_pulled,
                    records_inserted=log.records_inserted,
                    records_updated=log.records_updated,
                    conflicts_detected=log.conflicts_detected,
                    status=log.status,
                    duration_seconds=log.duration_seconds,
                ))
        return results


@app.get("/sync/logs", tags=["sync"])
def sync_logs(
    source: Optional[str] = Query(None, description="Filter by 'greenhouse' or 'workday'"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    """Returns paginated sync audit log."""
    with get_session() as session:
        q = session.query(SyncLog)
        if source:
            q = q.filter(SyncLog.source_system == source)
        total = q.count()
        logs = q.order_by(desc(SyncLog.synced_at)).offset(offset).limit(limit).all()
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "results": [
                {
                    "id": str(log.id),
                    "synced_at": log.synced_at.isoformat(),
                    "source_system": log.source_system,
                    "records_pulled": log.records_pulled,
                    "records_inserted": log.records_inserted,
                    "records_updated": log.records_updated,
                    "records_skipped": log.records_skipped,
                    "conflicts_detected": log.conflicts_detected,
                    "status": log.status,
                    "duration_seconds": log.duration_seconds,
                    "error_message": log.error_message,
                }
                for log in logs
            ],
        }


# --------------------------------------------------------------------------- #
#  Analytics endpoints
# --------------------------------------------------------------------------- #

def _get_kpi(session, kpi_name: str, snapshot_date: Optional[date] = None) -> list:
    q = session.query(KPISnapshot).filter(KPISnapshot.kpi_name == kpi_name)
    if snapshot_date:
        q = q.filter(KPISnapshot.snapshot_date == snapshot_date)
    else:
        latest = session.query(KPISnapshot.snapshot_date).filter(
            KPISnapshot.kpi_name == kpi_name
        ).order_by(desc(KPISnapshot.snapshot_date)).scalar()
        if latest:
            q = q.filter(KPISnapshot.snapshot_date == latest)
    return q.all()


@app.get("/analytics/headcount", response_model=list[KPIResponse], tags=["analytics"])
def get_headcount(snapshot_date: Optional[date] = None):
    """Active headcount by department."""
    with get_session() as session:
        rows = _get_kpi(session, "headcount", snapshot_date)
        return [KPIResponse(kpi_name=r.kpi_name, dimension=r.dimension,
                            value=r.value, unit=r.unit,
                            snapshot_date=str(r.snapshot_date)) for r in rows]


@app.get("/analytics/attrition", response_model=list[KPIResponse], tags=["analytics"])
def get_attrition(snapshot_date: Optional[date] = None):
    """Monthly attrition rate (last 12 months)."""
    with get_session() as session:
        rows = _get_kpi(session, "attrition_rate", snapshot_date)
        return [KPIResponse(kpi_name=r.kpi_name, dimension=r.dimension,
                            value=r.value, unit=r.unit,
                            snapshot_date=str(r.snapshot_date)) for r in rows]


@app.get("/analytics/diversity", response_model=list[KPIResponse], tags=["analytics"])
def get_diversity(snapshot_date: Optional[date] = None):
    """Gender diversity % by department."""
    with get_session() as session:
        rows = _get_kpi(session, "diversity_pct", snapshot_date)
        return [KPIResponse(kpi_name=r.kpi_name, dimension=r.dimension,
                            value=r.value, unit=r.unit,
                            snapshot_date=str(r.snapshot_date)) for r in rows]


@app.get("/analytics/tenure", response_model=list[KPIResponse], tags=["analytics"])
def get_tenure(snapshot_date: Optional[date] = None):
    """Average tenure in months by department."""
    with get_session() as session:
        rows = _get_kpi(session, "avg_tenure_months", snapshot_date)
        return [KPIResponse(kpi_name=r.kpi_name, dimension=r.dimension,
                            value=r.value, unit=r.unit,
                            snapshot_date=str(r.snapshot_date)) for r in rows]


@app.get("/analytics/data-quality", response_model=list[KPIResponse], tags=["analytics"])
def get_data_quality(snapshot_date: Optional[date] = None):
    """Data completeness % by field and source system."""
    with get_session() as session:
        rows = []
        for kpi in ["data_quality_email", "data_quality_department",
                    "data_quality_gender", "data_quality_hire_date"]:
            rows.extend(_get_kpi(session, kpi, snapshot_date))
        return [KPIResponse(kpi_name=r.kpi_name, dimension=r.dimension,
                            value=r.value, unit=r.unit,
                            snapshot_date=str(r.snapshot_date)) for r in rows]
