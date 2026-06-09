"""
analytics/data_generator.py
Generates synthetic HR data for both mock API servers and testing.

Produces:
  - Greenhouse-style JSON candidate records
  - Workday-style XML worker records
  - A cross-system overlap set (same logical employee in both systems)
    to test conflict resolution
"""

import json
import random
import uuid
from datetime import date, timedelta
from lxml import etree
from faker import Faker

fake = Faker("en_IN")   # Indian locale for realistic names/locations
random.seed(42)

DEPARTMENTS = [
    "Engineering", "Data Platform", "Product", "Design",
    "Sales", "Customer Success", "HR", "Finance", "Legal"
]

JOB_TITLES = {
    "Engineering": ["Software Engineer", "Senior Engineer", "Staff Engineer", "Engineering Manager"],
    "Data Platform": ["Data Engineer", "Analytics Engineer", "Data Scientist", "ML Engineer"],
    "Product": ["Product Manager", "Senior PM", "Director of Product"],
    "Design": ["UX Designer", "Product Designer", "Design Lead"],
    "Sales": ["Account Executive", "Sales Development Rep", "Sales Manager"],
    "Customer Success": ["Customer Success Manager", "Implementation Specialist", "Solutions Consultant"],
    "HR": ["HR Business Partner", "Recruiter", "HR Director"],
    "Finance": ["Financial Analyst", "Controller", "Finance Manager"],
    "Legal": ["Counsel", "Paralegal", "General Counsel"],
}

SALARY_BANDS = ["L1", "L2", "L3", "L4", "L5", "L6"]
GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]
ETHNICITIES = ["South Asian", "East Asian", "White", "Black", "Hispanic", "Middle Eastern", "Other"]
LOCATIONS = ["Bangalore", "Hyderabad", "Mumbai", "Delhi", "Chennai", "Pune", "Remote"]
STATUSES_GH = ["active", "hired", "rejected"]
STATUSES_WD = ["Active", "Terminated", "Leave_of_Absence"]


def random_hire_date() -> date:
    start = date(2018, 1, 1)
    end = date(2024, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def random_termination_date(hire_date: date) -> date | None:
    """30% chance of being terminated, 3-24 months after hire."""
    if random.random() > 0.30:
        return None
    months = random.randint(3, 24)
    return hire_date + timedelta(days=months * 30)


# --------------------------------------------------------------------------- #
#  Greenhouse JSON records
# --------------------------------------------------------------------------- #

def generate_greenhouse_record(employee_id: str = None) -> dict:
    dept = random.choice(DEPARTMENTS)
    hire_date = random_hire_date()
    term_date = random_termination_date(hire_date)

    return {
        "id": employee_id or f"gh-{fake.unique.random_int(min=1000, max=9999)}",
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email_addresses": [
            {"value": fake.email(), "type": "personal"}
        ],
        "employments": [
            {
                "title": random.choice(JOB_TITLES[dept]),
                "department": dept,
                "start_date": hire_date.isoformat(),
                "end_date": term_date.isoformat() if term_date else None,
            }
        ],
        "demographics": {
            "gender": random.choice(GENDERS),
            "race": random.choice(ETHNICITIES),
        },
        "office": {"name": random.choice(LOCATIONS)},
        "status": "active" if not term_date else "rejected",
        "application": {
            "rejected_at": term_date.isoformat() if term_date else None
        }
    }


def generate_greenhouse_dataset(n: int = 500) -> list[dict]:
    """Generates n Greenhouse candidate records."""
    return [generate_greenhouse_record() for _ in range(n)]


# --------------------------------------------------------------------------- #
#  Workday XML records
# --------------------------------------------------------------------------- #

def generate_workday_record_xml(worker_id: str = None) -> bytes:
    dept = random.choice(DEPARTMENTS)
    hire_date = random_hire_date()
    term_date = random_termination_date(hire_date)
    status = "Terminated" if term_date else "Active"

    worker = etree.Element("Worker", id=worker_id or f"WD-{fake.unique.random_int(min=2000, max=9999)}")

    personal = etree.SubElement(worker, "Personal_Data")
    name_el = etree.SubElement(personal, "Name")
    full_name = etree.SubElement(name_el, "Full_Name")
    full_name.text = fake.name()
    contact = etree.SubElement(personal, "Contact")
    email_el = etree.SubElement(contact, "Email")
    email_el.text = fake.email()
    demo = etree.SubElement(personal, "Demographics")
    gender_el = etree.SubElement(demo, "Gender")
    gender_el.text = random.choice(GENDERS)
    eth_el = etree.SubElement(demo, "Ethnicity")
    eth_el.text = random.choice(ETHNICITIES)

    emp = etree.SubElement(worker, "Employment_Data")
    pos = etree.SubElement(emp, "Position")
    for tag, val in [
        ("Title", random.choice(JOB_TITLES[dept])),
        ("Department", dept),
        ("Location", random.choice(LOCATIONS)),
        ("Hire_Date", hire_date.isoformat()),
        ("Termination_Date", term_date.isoformat() if term_date else ""),
        ("Salary_Band", random.choice(SALARY_BANDS)),
        ("Manager_ID", f"WD-{random.randint(1000, 1999)}"),
    ]:
        el = etree.SubElement(pos, tag)
        el.text = val
    status_el = etree.SubElement(emp, "Status")
    status_el.text = status

    return etree.tostring(worker, pretty_print=True, encoding="unicode").encode()


def generate_workday_dataset(n: int = 500) -> list[bytes]:
    return [generate_workday_record_xml() for _ in range(n)]


# --------------------------------------------------------------------------- #
#  CLI entrypoint
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import argparse, os

    parser = argparse.ArgumentParser(description="Generate synthetic HR data")
    parser.add_argument("--greenhouse-count", type=int, default=500)
    parser.add_argument("--workday-count", type=int, default=500)
    parser.add_argument("--output-dir", default="./mock_servers/data")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    gh_data = generate_greenhouse_dataset(args.greenhouse_count)
    gh_path = os.path.join(args.output_dir, "greenhouse_candidates.json")
    with open(gh_path, "w") as f:
        json.dump({"meta": {"total": len(gh_data)}, "candidates": gh_data}, f, indent=2)
    print(f"Generated {len(gh_data)} Greenhouse records → {gh_path}")

    wd_records = generate_workday_dataset(args.workday_count)
    wd_path = os.path.join(args.output_dir, "workday_workers.xml")
    with open(wd_path, "wb") as f:
        root = etree.Element("Workers", total=str(len(wd_records)))
        for rec in wd_records:
            root.append(etree.fromstring(rec))
        f.write(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
    print(f"Generated {len(wd_records)} Workday records  → {wd_path}")
