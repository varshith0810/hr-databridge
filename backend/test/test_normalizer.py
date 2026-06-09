"""
tests/test_normalizer.py
Unit tests for SchemaNormalizer and ConflictResolver.
Run: pytest tests/test_normalizer.py -v
"""

import pytest
from datetime import date
from ingestion.schema_normalizer import SchemaNormalizer, ConflictResolver
from storage.models import Employee


def _make_parsed(overrides=None) -> dict:
    base = {
        "employee_id": "gh-1001",
        "source_system": "greenhouse",
        "full_name": "Anita Sharma",
        "email": "anita@example.com",
        "department": "Engineering",
        "job_title": "Data Engineer",
        "location": "Bangalore",
        "status": "active",
        "gender": "Female",
        "ethnicity": "South Asian",
        "hire_date": "2022-03-01",
        "termination_date": None,
        "manager_id": None,
        "salary_band": None,
    }
    if overrides:
        base.update(overrides)
    return base


def _make_employee(overrides=None) -> Employee:
    parsed = _make_parsed(overrides)
    return SchemaNormalizer.normalize(parsed)


# ------------------------------------------------------------------ #
#  SchemaNormalizer tests
# ------------------------------------------------------------------ #

def test_normalizer_basic():
    emp = _make_employee()
    assert emp.employee_id == "gh-1001"
    assert emp.source_system == "greenhouse"
    assert emp.full_name == "Anita Sharma"
    assert emp.department == "Engineering"
    assert emp.hire_date == date(2022, 3, 1)
    assert emp.status == "active"


def test_normalizer_date_parsing_various_formats():
    emp = _make_employee({"hire_date": "01/03/2022"})
    assert emp.hire_date == date(2022, 1, 3)    # MM/DD/YYYY

    emp2 = _make_employee({"hire_date": "2022-03-01T00:00:00"})
    assert emp2.hire_date == date(2022, 3, 1)


def test_normalizer_null_date():
    emp = _make_employee({"termination_date": None})
    assert emp.termination_date is None


def test_normalizer_invalid_date_becomes_none():
    emp = _make_employee({"hire_date": "not-a-date"})
    assert emp.hire_date is None


def test_normalizer_missing_name_defaults():
    emp = _make_employee({"full_name": None})
    assert emp.full_name == "Unknown"


def test_normalizer_missing_employee_id_raises():
    parsed = _make_parsed({"employee_id": None})
    with pytest.raises(ValueError, match="employee_id"):
        SchemaNormalizer.normalize(parsed)


def test_normalizer_missing_source_system_raises():
    parsed = _make_parsed({"source_system": None})
    with pytest.raises(ValueError, match="source_system"):
        SchemaNormalizer.normalize(parsed)


# ------------------------------------------------------------------ #
#  ConflictResolver tests
# ------------------------------------------------------------------ #

def _gh_employee() -> Employee:
    return _make_employee({
        "employee_id": "gh-1001",
        "source_system": "greenhouse",
        "full_name": "Anita Sharma",
        "email": "anita@gh.com",
        "department": "Data",
        "job_title": "Analyst",
        "status": "active",
        "gender": "Female",
        "ethnicity": "South Asian",
        "hire_date": "2022-03-01",
        "salary_band": None,
    })


def _wd_employee() -> Employee:
    return _make_employee({
        "employee_id": "WD-2001",
        "source_system": "workday",
        "full_name": "Anita Sharma",
        "email": "anita@wd.com",
        "department": "Data Platform",
        "job_title": "Data Engineer",
        "status": "active",
        "gender": None,
        "ethnicity": None,
        "hire_date": "2022-03-01",
        "salary_band": "L4",
    })


def test_conflict_resolver_workday_wins_on_employment_fields():
    merged, detail = ConflictResolver.resolve(_gh_employee(), _wd_employee())
    assert merged.department == "Data Platform"   # Workday wins
    assert merged.job_title == "Data Engineer"    # Workday wins
    assert merged.salary_band == "L4"             # Workday wins


def test_conflict_resolver_greenhouse_wins_on_demographics():
    merged, detail = ConflictResolver.resolve(_gh_employee(), _wd_employee())
    assert merged.email == "anita@gh.com"         # Greenhouse wins
    assert merged.gender == "Female"              # Greenhouse wins
    assert merged.ethnicity == "South Asian"      # Greenhouse wins


def test_conflict_resolver_returns_workday_source_system():
    merged, _ = ConflictResolver.resolve(_gh_employee(), _wd_employee())
    assert merged.source_system == "workday"


def test_conflict_resolver_logs_conflicting_fields():
    _, detail = ConflictResolver.resolve(_gh_employee(), _wd_employee())
    field_names = [c["field"] for c in detail["conflicting_fields"]]
    assert "department" in field_names
    assert "job_title" in field_names


def test_conflict_resolver_no_conflict_when_data_matches():
    gh = _gh_employee()
    wd = _wd_employee()
    wd.department = gh.department    # Make them match
    wd.job_title = gh.job_title
    _, detail = ConflictResolver.resolve(gh, wd)
    field_names = [c["field"] for c in detail["conflicting_fields"]]
    assert "department" not in field_names
    assert "job_title" not in field_names
