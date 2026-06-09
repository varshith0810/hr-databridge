"""
ingestion/payload_parser.py
Converts raw API payloads (JSON dict or XML bytes) into
intermediate Python dicts with a predictable key set.

This is a pure transform layer — no DB writes happen here.
The schema_normalizer then maps these intermediate dicts
to the unified Employee model.
"""

import logging
from typing import Optional
from lxml import etree

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Intermediate schema (common dict shape for both sources)
# --------------------------------------------------------------------------- #

def _empty_record() -> dict:
    return {
        "employee_id": None,
        "source_system": None,
        "full_name": None,
        "email": None,
        "department": None,
        "job_title": None,
        "location": None,
        "status": None,
        "gender": None,
        "ethnicity": None,
        "hire_date": None,
        "termination_date": None,
        "manager_id": None,
        "salary_band": None,
        "_raw_source": None,    # For debugging; not persisted
    }


# --------------------------------------------------------------------------- #
#  Greenhouse JSON parser
# --------------------------------------------------------------------------- #

class GreenhouseParser:
    """
    Parses a raw Greenhouse candidate JSON dict.

    Greenhouse candidate structure (simplified mock):
    {
      "id": "gh-1001",
      "first_name": "Anita",
      "last_name": "Sharma",
      "email_addresses": [{"value": "anita@example.com", "type": "personal"}],
      "employments": [{
        "title": "Senior Engineer",
        "start_date": "2022-03-01",
        "end_date": null,
        "department": "Engineering"
      }],
      "demographics": {
        "gender": "Female",
        "race": "Asian"
      },
      "office": {"name": "Bangalore"},
      "status": "active",
      "application": {"rejected_at": null}
    }
    """

    @staticmethod
    def parse(raw: dict) -> dict:
        """
        Converts a Greenhouse candidate dict to the intermediate schema.

        Args:
            raw: Raw JSON dict from Greenhouse API

        Returns:
            Intermediate dict with unified keys

        Raises:
            ValueError: if required fields are missing or malformed
        """
        if not raw.get("id"):
            raise ValueError(f"Greenhouse record missing 'id': {raw}")

        record = _empty_record()
        record["source_system"] = "greenhouse"
        record["_raw_source"] = raw

        try:
            record["employee_id"] = str(raw["id"])

            # Name
            first = raw.get("first_name", "").strip()
            last = raw.get("last_name", "").strip()
            record["full_name"] = f"{first} {last}".strip() or None

            # Email — take first personal or first available
            emails = raw.get("email_addresses", [])
            if emails:
                personal = next((e["value"] for e in emails if e.get("type") == "personal"), None)
                record["email"] = personal or emails[0].get("value")

            # Employment (latest entry)
            employments = raw.get("employments", [])
            if employments:
                latest = employments[-1]
                record["job_title"] = latest.get("title")
                record["department"] = latest.get("department")
                record["hire_date"] = latest.get("start_date")
                record["termination_date"] = latest.get("end_date")

            # Status — map Greenhouse's "active"/"rejected"/"hired" to our enum
            gh_status = raw.get("status", "").lower()
            status_map = {
                "active": "active",
                "hired": "active",
                "rejected": "terminated",
                "withdrawn": "terminated",
            }
            record["status"] = status_map.get(gh_status, "active")

            # Override: if rejected_at is set, mark terminated
            if raw.get("application", {}).get("rejected_at"):
                record["status"] = "terminated"

            # Demographics
            demo = raw.get("demographics", {})
            record["gender"] = demo.get("gender")
            record["ethnicity"] = demo.get("race")

            # Location
            office = raw.get("office", {})
            record["location"] = office.get("name")

        except Exception as exc:
            logger.error(f"[GreenhouseParser] Failed to parse record {raw.get('id')}: {exc}")
            raise ValueError(f"Parse error for Greenhouse record {raw.get('id')}: {exc}") from exc

        return record


# --------------------------------------------------------------------------- #
#  Workday XML parser
# --------------------------------------------------------------------------- #

class WorkdayParser:
    """
    Parses a raw Workday <Worker> XML element.

    Workday XML structure (simplified mock):
    <Worker id="WD-2001">
      <Personal_Data>
        <Name><Full_Name>Rajesh Kumar</Full_Name></Name>
        <Contact>
          <Email>rajesh@example.com</Email>
        </Contact>
        <Demographics>
          <Gender>Male</Gender>
          <Ethnicity>South Asian</Ethnicity>
        </Demographics>
      </Personal_Data>
      <Employment_Data>
        <Position>
          <Title>Data Engineer</Title>
          <Department>Data Platform</Department>
          <Location>Hyderabad</Location>
          <Hire_Date>2021-06-15</Hire_Date>
          <Termination_Date/>
          <Salary_Band>L4</Salary_Band>
          <Manager_ID>WD-1005</Manager_ID>
        </Position>
        <Status>Active</Status>
      </Employment_Data>
    </Worker>
    """

    @staticmethod
    def _text(element, xpath: str) -> Optional[str]:
        """Safe XPath text extractor — returns None if element missing or empty."""
        node = element.find(xpath)
        if node is not None and node.text:
            return node.text.strip() or None
        return None

    @classmethod
    def parse(cls, xml_bytes: bytes) -> dict:
        """
        Converts a Workday Worker XML element to the intermediate schema.

        Args:
            xml_bytes: Raw <Worker>...</Worker> XML as bytes

        Returns:
            Intermediate dict with unified keys

        Raises:
            ValueError: if required fields are missing or XML is malformed
        """
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Malformed XML from Workday: {exc}") from exc

        worker_id = root.get("id")
        if not worker_id:
            raise ValueError("Workday <Worker> element missing 'id' attribute")

        record = _empty_record()
        record["source_system"] = "workday"
        record["_raw_source"] = xml_bytes.decode("utf-8", errors="replace")

        try:
            record["employee_id"] = worker_id
            record["full_name"] = cls._text(root, "Personal_Data/Name/Full_Name")
            record["email"] = cls._text(root, "Personal_Data/Contact/Email")
            record["gender"] = cls._text(root, "Personal_Data/Demographics/Gender")
            record["ethnicity"] = cls._text(root, "Personal_Data/Demographics/Ethnicity")
            record["job_title"] = cls._text(root, "Employment_Data/Position/Title")
            record["department"] = cls._text(root, "Employment_Data/Position/Department")
            record["location"] = cls._text(root, "Employment_Data/Position/Location")
            record["hire_date"] = cls._text(root, "Employment_Data/Position/Hire_Date")
            record["termination_date"] = cls._text(root, "Employment_Data/Position/Termination_Date")
            record["salary_band"] = cls._text(root, "Employment_Data/Position/Salary_Band")
            record["manager_id"] = cls._text(root, "Employment_Data/Position/Manager_ID")

            # Status — map Workday "Active"/"Terminated"/"Leave_of_Absence" to our enum
            wd_status = (cls._text(root, "Employment_Data/Status") or "").lower()
            status_map = {
                "active": "active",
                "terminated": "terminated",
                "leave_of_absence": "on_leave",
                "on leave": "on_leave",
            }
            record["status"] = status_map.get(wd_status, "active")

        except Exception as exc:
            logger.error(f"[WorkdayParser] Failed to parse Worker {worker_id}: {exc}")
            raise ValueError(f"Parse error for Workday Worker {worker_id}: {exc}") from exc

        return record
