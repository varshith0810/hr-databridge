"""
ingestion/schema_normalizer.py
Maps intermediate parsed dicts to SQLAlchemy Employee ORM objects.

Also handles conflict resolution when the same logical employee
exists in both Greenhouse and Workday:
  - Rule: Workday (HRIS) is the source of truth for employment data.
  - Greenhouse wins for: recruitment metadata, email, demographics.
  - Conflict = same business-key employee found in both systems.
"""

import logging
from datetime import date, datetime
from typing import Optional
from storage.models import Employee

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Date coercion
# --------------------------------------------------------------------------- #

def _to_date(value: Optional[str]) -> Optional[date]:
    """
    Coerces a date string (ISO-8601 or YYYY-MM-DD) to a Python date.
    Returns None if value is empty, null, or unparseable.
    """
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y"):
        try:
            return datetime.strptime(value[:10], fmt[:8]).date()
        except (ValueError, TypeError):
            continue
    logger.warning(f"Could not parse date value: {value!r} — setting to None")
    return None


# --------------------------------------------------------------------------- #
#  Normalizer
# --------------------------------------------------------------------------- #

class SchemaNormalizer:
    """
    Converts an intermediate parsed dict (from payload_parser.py)
    into a storage.models.Employee ORM object, ready for upsert.
    """

    @staticmethod
    def normalize(parsed: dict) -> Employee:
        """
        Maps a parsed record to an Employee ORM model instance.

        Args:
            parsed: Intermediate dict produced by GreenhouseParser or WorkdayParser

        Returns:
            Employee ORM object (not yet written to DB)

        Raises:
            ValueError: if employee_id or source_system are missing
        """
        if not parsed.get("employee_id"):
            raise ValueError(f"Cannot normalize record without employee_id: {parsed}")
        if not parsed.get("source_system"):
            raise ValueError(f"Cannot normalize record without source_system: {parsed}")

        return Employee(
            employee_id=parsed["employee_id"],
            source_system=parsed["source_system"],
            full_name=parsed.get("full_name") or "Unknown",
            email=parsed.get("email"),
            department=parsed.get("department"),
            job_title=parsed.get("job_title"),
            location=parsed.get("location"),
            status=parsed.get("status") or "active",
            gender=parsed.get("gender"),
            ethnicity=parsed.get("ethnicity"),
            hire_date=_to_date(parsed.get("hire_date")),
            termination_date=_to_date(parsed.get("termination_date")),
            manager_id=parsed.get("manager_id"),
            salary_band=parsed.get("salary_band"),
            last_synced_at=datetime.utcnow(),
        )


# --------------------------------------------------------------------------- #
#  Conflict resolver
# --------------------------------------------------------------------------- #

class ConflictResolver:
    """
    Detects and resolves conflicts when an employee appears in both systems.

    Conflict detection:
      An employee is considered a match across systems if their
      full_name AND hire_date are identical (since employee IDs
      differ between Greenhouse and Workday).

    Resolution strategy (Workday wins):
      Workday (HRIS) fields: job_title, department, location,
                              hire_date, termination_date, status,
                              salary_band, manager_id
      Greenhouse fields:     email, gender, ethnicity (better data quality)
    """

    @staticmethod
    def resolve(
        greenhouse_record: Employee,
        workday_record: Employee,
    ) -> tuple[Employee, dict]:
        """
        Merges a Greenhouse and Workday record into a single authoritative Employee.

        Args:
            greenhouse_record: Employee from Greenhouse
            workday_record:    Employee from Workday (takes priority)

        Returns:
            Tuple of (merged Employee, conflict_detail dict for audit log)
        """
        conflict_fields = []

        # Fields where Workday wins
        wd_fields = ["job_title", "department", "location", "hire_date",
                     "termination_date", "status", "salary_band", "manager_id"]

        merged = Employee(
            employee_id=workday_record.employee_id,
            source_system="workday",           # Canonical source after merge
            full_name=workday_record.full_name or greenhouse_record.full_name,
            last_synced_at=datetime.utcnow(),
        )

        for field in wd_fields:
            wd_val = getattr(workday_record, field)
            gh_val = getattr(greenhouse_record, field)
            setattr(merged, field, wd_val)

            if wd_val != gh_val and gh_val is not None:
                conflict_fields.append({
                    "field": field,
                    "greenhouse_value": str(gh_val),
                    "workday_value": str(wd_val),
                    "resolved_to": "workday",
                })

        # Fields where Greenhouse wins (richer demographic data)
        merged.email = greenhouse_record.email or workday_record.email
        merged.gender = greenhouse_record.gender or workday_record.gender
        merged.ethnicity = greenhouse_record.ethnicity or workday_record.ethnicity

        conflict_detail = {
            "greenhouse_id": greenhouse_record.employee_id,
            "workday_id": workday_record.employee_id,
            "employee_name": merged.full_name,
            "conflicting_fields": conflict_fields,
            "resolution": "workday_wins_on_employment_greenhouse_wins_on_demographics",
        }

        if conflict_fields:
            logger.info(
                f"[ConflictResolver] Resolved {len(conflict_fields)} field conflicts "
                f"for employee '{merged.full_name}' — Workday wins on employment data."
            )

        return merged, conflict_detail
