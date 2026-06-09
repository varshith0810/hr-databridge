"""
scheduler/dag_sync.py
Apache Airflow DAG: HR DataBridge Sync Pipeline

Task order (each runs sequentially, fails fast):
  poll_greenhouse → parse_greenhouse → upsert_greenhouse →
  poll_workday    → parse_workday    → upsert_workday    →
  run_conflict_resolution → run_kpi_engine

Schedule: every 15 minutes.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "hr-databridge",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
    "email_on_failure": False,
}


# --------------------------------------------------------------------------- #
#  Task functions
# --------------------------------------------------------------------------- #

def task_poll_and_sync_greenhouse(**context):
    """Poll Greenhouse API and upsert normalized records to PostgreSQL."""
    from ingestion.api_poller import GreenhousePoller
    from ingestion.payload_parser import GreenhouseParser
    from ingestion.schema_normalizer import SchemaNormalizer
    from ingestion.delta_tracker import DeltaTracker
    from storage.db import get_session
    from storage.models import Employee

    start_time = time.time()
    poller = GreenhousePoller()
    stats = dict(pulled=0, inserted=0, updated=0, skipped=0, errors=0)

    try:
        with get_session() as session:
            tracker = DeltaTracker(session)
            cursor = tracker.get_last_cursor("greenhouse")
            next_cursor = poller.get_next_cursor()

            for raw in poller.fetch_since(cursor=cursor):
                stats["pulled"] += 1
                try:
                    parsed = GreenhouseParser.parse(raw)
                    employee = SchemaNormalizer.normalize(parsed)

                    # Check for existing record
                    existing = (
                        session.query(Employee)
                        .filter_by(employee_id=employee.employee_id, source_system="greenhouse")
                        .first()
                    )

                    if existing:
                        for field in ["full_name", "email", "department", "job_title",
                                      "status", "gender", "ethnicity", "location",
                                      "hire_date", "termination_date"]:
                            setattr(existing, field, getattr(employee, field))
                        existing.last_synced_at = employee.last_synced_at
                        stats["updated"] += 1
                    else:
                        session.add(employee)
                        stats["inserted"] += 1

                except Exception as exc:
                    logger.error(f"[Greenhouse] Failed to process record: {exc}")
                    stats["errors"] += 1
                    stats["skipped"] += 1

            duration = time.time() - start_time
            tracker.write_sync_log(
                source_system="greenhouse",
                cursor_used=cursor,
                cursor_next=next_cursor,
                records_pulled=stats["pulled"],
                records_inserted=stats["inserted"],
                records_updated=stats["updated"],
                records_skipped=stats["skipped"],
                conflicts_detected=0,
                conflicts_resolved=0,
                duration_seconds=duration,
                status="success" if stats["errors"] == 0 else "partial",
            )

        logger.info(f"[Greenhouse] Sync complete: {stats}")
        context["task_instance"].xcom_push(key="greenhouse_stats", value=stats)

    finally:
        poller.close()


def task_poll_and_sync_workday(**context):
    """Poll Workday API and upsert normalized records to PostgreSQL."""
    from ingestion.api_poller import WorkdayPoller
    from ingestion.payload_parser import WorkdayParser
    from ingestion.schema_normalizer import SchemaNormalizer
    from ingestion.delta_tracker import DeltaTracker
    from storage.db import get_session
    from storage.models import Employee

    start_time = time.time()
    poller = WorkdayPoller()
    stats = dict(pulled=0, inserted=0, updated=0, skipped=0, errors=0)

    try:
        with get_session() as session:
            tracker = DeltaTracker(session)
            cursor = tracker.get_last_cursor("workday")
            next_cursor = poller.get_next_cursor()

            for xml_bytes in poller.fetch_since(cursor=cursor):
                stats["pulled"] += 1
                try:
                    parsed = WorkdayParser.parse(xml_bytes)
                    employee = SchemaNormalizer.normalize(parsed)

                    existing = (
                        session.query(Employee)
                        .filter_by(employee_id=employee.employee_id, source_system="workday")
                        .first()
                    )

                    if existing:
                        for field in ["full_name", "email", "department", "job_title",
                                      "status", "gender", "ethnicity", "location",
                                      "hire_date", "termination_date", "salary_band", "manager_id"]:
                            setattr(existing, field, getattr(employee, field))
                        existing.last_synced_at = employee.last_synced_at
                        stats["updated"] += 1
                    else:
                        session.add(employee)
                        stats["inserted"] += 1

                except Exception as exc:
                    logger.error(f"[Workday] Failed to process record: {exc}")
                    stats["errors"] += 1
                    stats["skipped"] += 1

            duration = time.time() - start_time
            tracker.write_sync_log(
                source_system="workday",
                cursor_used=cursor,
                cursor_next=next_cursor,
                records_pulled=stats["pulled"],
                records_inserted=stats["inserted"],
                records_updated=stats["updated"],
                records_skipped=stats["skipped"],
                conflicts_detected=0,
                conflicts_resolved=0,
                duration_seconds=duration,
                status="success" if stats["errors"] == 0 else "partial",
            )

        logger.info(f"[Workday] Sync complete: {stats}")
        context["task_instance"].xcom_push(key="workday_stats", value=stats)

    finally:
        poller.close()


def task_run_kpi_engine(**context):
    """Recompute all KPI snapshots after both sources have synced."""
    from analytics.kpi_engine import KPIEngine
    from storage.db import get_session

    with get_session() as session:
        engine = KPIEngine(session)
        summary = engine.run_all()

    logger.info(f"[KPIEngine] Run complete: {summary}")
    context["task_instance"].xcom_push(key="kpi_summary", value=summary)


# --------------------------------------------------------------------------- #
#  DAG definition
# --------------------------------------------------------------------------- #

with DAG(
    dag_id="hr_databridge_sync",
    default_args=DEFAULT_ARGS,
    description="Sync Greenhouse + Workday → PostgreSQL, then compute KPIs",
    schedule_interval="*/15 * * * *",      # Every 15 minutes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,                     # Prevent overlapping sync runs
    tags=["hr", "integration", "analytics"],
) as dag:

    sync_greenhouse = PythonOperator(
        task_id="sync_greenhouse",
        python_callable=task_poll_and_sync_greenhouse,
    )

    sync_workday = PythonOperator(
        task_id="sync_workday",
        python_callable=task_poll_and_sync_workday,
    )

    run_kpi = PythonOperator(
        task_id="run_kpi_engine",
        python_callable=task_run_kpi_engine,
    )

    # Both sources sync in parallel, then KPIs run after both finish
    [sync_greenhouse, sync_workday] >> run_kpi
