"""
analytics/kpi_engine.py
Executes the KPI SQL queries from kpi_queries.sql and writes
results to the kpi_snapshots table.

Called at the end of every sync cycle (via Airflow DAG).
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from storage.models import KPISnapshot

logger = logging.getLogger(__name__)

SQL_FILE = Path(__file__).parent / "kpi_queries.sql"


def _load_query(name: str) -> str:
    """
    Extracts a named query from kpi_queries.sql using the
    [query_name] marker comment convention.

    Args:
        name: Query block name (e.g. 'headcount_by_department')

    Returns:
        SQL string for that query block

    Raises:
        KeyError: if the named block doesn't exist in the file
    """
    sql_text = SQL_FILE.read_text()
    blocks = {}
    current_name = None
    current_lines = []

    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- [") and stripped.endswith("]"):
            if current_name:
                blocks[current_name] = "\n".join(current_lines).strip()
            current_name = stripped[4:-1]
            current_lines = []
        elif current_name:
            # Stop block at next named comment or end-of-file
            if stripped.startswith("-- [") and stripped.endswith("]"):
                break
            if not stripped.startswith("--"):
                current_lines.append(line)

    if current_name:
        blocks[current_name] = "\n".join(current_lines).strip()

    if name not in blocks:
        raise KeyError(f"Query block '{name}' not found in kpi_queries.sql")

    return blocks[name]


def _upsert_snapshot(
    session: Session,
    snapshot_date: date,
    kpi_name: str,
    dimension: str,
    value: float,
    unit: Optional[str] = None,
) -> None:
    """
    Inserts or updates a KPISnapshot row.
    Uses PostgreSQL ON CONFLICT for true upsert.
    """
    session.execute(
        text("""
            INSERT INTO kpi_snapshots (id, snapshot_date, kpi_name, dimension, value, unit, computed_at)
            VALUES (gen_random_uuid(), :snap_date, :kpi_name, :dimension, :value, :unit, NOW())
            ON CONFLICT (snapshot_date, kpi_name, dimension)
            DO UPDATE SET
                value = EXCLUDED.value,
                computed_at = NOW()
        """),
        {
            "snap_date": snapshot_date,
            "kpi_name": kpi_name,
            "dimension": dimension,
            "value": value,
            "unit": unit,
        },
    )


class KPIEngine:
    """
    Orchestrates running all KPI queries and persisting results.
    """

    def __init__(self, session: Session):
        self.session = session
        self.today = date.today()

    def run_all(self) -> dict:
        """
        Runs all KPI queries and writes snapshots to DB.

        Returns:
            Summary dict: { kpi_name: row_count_written }
        """
        summary = {}
        runners = [
            ("headcount_by_department", self._run_headcount),
            ("attrition_rate_monthly", self._run_attrition),
            ("diversity_by_department", self._run_diversity),
            ("avg_tenure_by_department", self._run_tenure),
            ("headcount_trend_monthly", self._run_headcount_trend),
            ("top_roles", self._run_top_roles),
            ("new_hires_mtd", self._run_new_hires),
            ("data_quality_by_source", self._run_data_quality),
        ]

        for query_name, runner in runners:
            try:
                count = runner()
                summary[query_name] = count
                logger.info(f"[KPIEngine] {query_name}: {count} snapshots written")
            except Exception as exc:
                logger.error(f"[KPIEngine] Failed on {query_name}: {exc}")
                summary[query_name] = f"ERROR: {exc}"

        return summary

    def _run_headcount(self) -> int:
        rows = self.session.execute(text(_load_query("headcount_by_department"))).fetchall()
        for row in rows:
            _upsert_snapshot(self.session, self.today, "headcount", row.department, float(row.headcount), "count")
        return len(rows)

    def _run_attrition(self) -> int:
        rows = self.session.execute(text(_load_query("attrition_rate_monthly"))).fetchall()
        for row in rows:
            _upsert_snapshot(self.session, self.today, "attrition_rate", row.month, float(row.attrition_rate_pct), "percent")
        return len(rows)

    def _run_diversity(self) -> int:
        rows = self.session.execute(text(_load_query("diversity_by_department"))).fetchall()
        for row in rows:
            dimension = f"{row.department}::{row.gender}"
            _upsert_snapshot(self.session, self.today, "diversity_pct", dimension, float(row.pct_of_dept), "percent")
        return len(rows)

    def _run_tenure(self) -> int:
        rows = self.session.execute(text(_load_query("avg_tenure_by_department"))).fetchall()
        for row in rows:
            _upsert_snapshot(self.session, self.today, "avg_tenure_months", row.department, float(row.avg_tenure_months), "months")
        return len(rows)

    def _run_headcount_trend(self) -> int:
        rows = self.session.execute(text(_load_query("headcount_trend_monthly"))).fetchall()
        for row in rows:
            _upsert_snapshot(self.session, self.today, "headcount_trend", row.month, float(row.headcount), "count")
        return len(rows)

    def _run_top_roles(self) -> int:
        rows = self.session.execute(text(_load_query("top_roles"))).fetchall()
        for row in rows:
            _upsert_snapshot(self.session, self.today, "top_roles_headcount", row.job_title, float(row.headcount), "count")
        return len(rows)

    def _run_new_hires(self) -> int:
        row = self.session.execute(text(_load_query("new_hires_mtd"))).fetchone()
        if row:
            _upsert_snapshot(self.session, self.today, "new_hires_mtd", row.month, float(row.new_hires), "count")
        return 1 if row else 0

    def _run_data_quality(self) -> int:
        rows = self.session.execute(text(_load_query("data_quality_by_source"))).fetchall()
        for row in rows:
            for field, metric in [
                ("email_completeness_pct", "email"),
                ("dept_completeness_pct", "department"),
                ("gender_completeness_pct", "gender"),
                ("hiredate_completeness_pct", "hire_date"),
            ]:
                _upsert_snapshot(
                    self.session, self.today,
                    f"data_quality_{metric}",
                    row.source_system,
                    float(getattr(row, field)),
                    "percent"
                )
        return len(rows) * 4
