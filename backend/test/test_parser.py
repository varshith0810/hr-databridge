"""
tests/test_parser.py
Unit tests for GreenhouseParser and WorkdayParser.
Run: pytest tests/test_parser.py -v
"""

import pytest
from lxml import etree
from ingestion.payload_parser import GreenhouseParser, WorkdayParser


# ------------------------------------------------------------------ #
#  Greenhouse Parser tests
# ------------------------------------------------------------------ #

VALID_GH_RECORD = {
    "id": "gh-1001",
    "first_name": "Anita",
    "last_name": "Sharma",
    "email_addresses": [{"value": "anita@example.com", "type": "personal"}],
    "employments": [{
        "title": "Data Engineer",
        "department": "Data Platform",
        "start_date": "2022-03-01",
        "end_date": None,
    }],
    "demographics": {"gender": "Female", "race": "South Asian"},
    "office": {"name": "Bangalore"},
    "status": "active",
    "application": {"rejected_at": None},
}


def test_greenhouse_parser_happy_path():
    result = GreenhouseParser.parse(VALID_GH_RECORD)
    assert result["employee_id"] == "gh-1001"
    assert result["source_system"] == "greenhouse"
    assert result["full_name"] == "Anita Sharma"
    assert result["email"] == "anita@example.com"
    assert result["department"] == "Data Platform"
    assert result["job_title"] == "Data Engineer"
    assert result["status"] == "active"
    assert result["gender"] == "Female"
    assert result["ethnicity"] == "South Asian"
    assert result["hire_date"] == "2022-03-01"
    assert result["location"] == "Bangalore"


def test_greenhouse_parser_terminated_by_rejected_at():
    record = dict(VALID_GH_RECORD, status="active")
    record["application"] = {"rejected_at": "2023-06-15"}
    result = GreenhouseParser.parse(record)
    assert result["status"] == "terminated"


def test_greenhouse_parser_status_mapping():
    for gh_status, expected in [("rejected", "terminated"), ("withdrawn", "terminated"), ("hired", "active")]:
        r = dict(VALID_GH_RECORD, status=gh_status)
        r["application"] = {"rejected_at": None}
        result = GreenhouseParser.parse(r)
        assert result["status"] == expected, f"Failed for {gh_status}"


def test_greenhouse_parser_missing_id_raises():
    bad = dict(VALID_GH_RECORD)
    bad.pop("id")
    with pytest.raises(ValueError, match="missing 'id'"):
        GreenhouseParser.parse(bad)


def test_greenhouse_parser_missing_optional_fields():
    """Parser should not crash when optional fields are absent."""
    minimal = {"id": "gh-9999", "status": "active", "application": {}}
    result = GreenhouseParser.parse(minimal)
    assert result["employee_id"] == "gh-9999"
    assert result["email"] is None
    assert result["department"] is None


# ------------------------------------------------------------------ #
#  Workday Parser tests
# ------------------------------------------------------------------ #

VALID_WD_XML = b"""
<Worker id="WD-2001">
  <Personal_Data>
    <Name><Full_Name>Rajesh Kumar</Full_Name></Name>
    <Contact><Email>rajesh@example.com</Email></Contact>
    <Demographics>
      <Gender>Male</Gender>
      <Ethnicity>South Asian</Ethnicity>
    </Demographics>
  </Personal_Data>
  <Employment_Data>
    <Position>
      <Title>Senior Engineer</Title>
      <Department>Engineering</Department>
      <Location>Hyderabad</Location>
      <Hire_Date>2021-06-15</Hire_Date>
      <Termination_Date></Termination_Date>
      <Salary_Band>L4</Salary_Band>
      <Manager_ID>WD-1005</Manager_ID>
    </Position>
    <Status>Active</Status>
  </Employment_Data>
</Worker>
"""


def test_workday_parser_happy_path():
    result = WorkdayParser.parse(VALID_WD_XML)
    assert result["employee_id"] == "WD-2001"
    assert result["source_system"] == "workday"
    assert result["full_name"] == "Rajesh Kumar"
    assert result["email"] == "rajesh@example.com"
    assert result["department"] == "Engineering"
    assert result["job_title"] == "Senior Engineer"
    assert result["status"] == "active"
    assert result["hire_date"] == "2021-06-15"
    assert result["termination_date"] is None
    assert result["salary_band"] == "L4"
    assert result["manager_id"] == "WD-1005"


def test_workday_parser_terminated_status():
    xml = VALID_WD_XML.replace(b"<Status>Active</Status>", b"<Status>Terminated</Status>")
    result = WorkdayParser.parse(xml)
    assert result["status"] == "terminated"


def test_workday_parser_on_leave_status():
    xml = VALID_WD_XML.replace(b"<Status>Active</Status>", b"<Status>Leave_of_Absence</Status>")
    result = WorkdayParser.parse(xml)
    assert result["status"] == "on_leave"


def test_workday_parser_missing_id_raises():
    xml = b"<Worker><Employment_Data/></Worker>"
    with pytest.raises(ValueError, match="missing 'id'"):
        WorkdayParser.parse(xml)


def test_workday_parser_malformed_xml_raises():
    with pytest.raises(ValueError, match="Malformed XML"):
        WorkdayParser.parse(b"<not valid xml")


def test_workday_parser_missing_optional_fields():
    xml = b'<Worker id="WD-0001"><Personal_Data/><Employment_Data><Status>Active</Status></Employment_Data></Worker>'
    result = WorkdayParser.parse(xml)
    assert result["employee_id"] == "WD-0001"
    assert result["full_name"] is None
    assert result["department"] is None
