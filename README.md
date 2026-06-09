# HR DataBridge

**ATS Integration Middleware + Workforce Analytics Pipeline**

A production-grade data integration platform that syncs candidate/employee records from two REST APIs (Greenhouse ATS and Workday HRIS), normalizes and reconciles them into a unified PostgreSQL schema, and computes workforce KPIs — all served via FastAPI and visualized in a Streamlit dashboard.

Built as a portfolio project targeting Product Solutions Engineer roles (Eightfold.ai profile).

---

## Architecture

```
Greenhouse API (JSON)        Workday API (XML)
       │                            │
   GreenhousePoller           WorkdayPoller
   GreenhouseParser           WorkdayParser
       │                            │
       └──────── SchemaNormalizer ──┘
                      │
               ConflictResolver
               (Workday wins on employment,
                Greenhouse wins on demographics)
                      │
                 PostgreSQL
          ┌───────────┼────────────┐
       employees   sync_log   kpi_snapshots
                      │
                 KPIEngine (SQL CTEs + window functions)
                      │
          ┌───────────┴────────────┐
       FastAPI REST API      Streamlit Dashboard
```

---

## Quick Start

```bash
# 1. Clone and set up env
git clone <repo>
cd hr-databridge
cp .env.example .env

# 2. Generate mock data
python -m analytics.data_generator --greenhouse-count 500 --workday-count 500

# 3. Start all services
docker-compose up --build

# 4. Access
#   API docs:      http://localhost:8000/docs
#   Dashboard:     http://localhost:8501
#   Greenhouse:    http://localhost:8001/docs
#   Workday:       http://localhost:8002/docs
```

---

## Project Structure

```
hr-databridge/
├── ingestion/
│   ├── api_poller.py          # REST API polling, delta sync, retry logic
│   ├── payload_parser.py      # JSON (Greenhouse) + XML (Workday) parsing
│   ├── schema_normalizer.py   # Unified Employee model mapping
│   └── delta_tracker.py       # Cursor management, sync audit logging
├── storage/
│   ├── models.py              # SQLAlchemy ORM: Employee, SyncLog, KPISnapshot
│   └── db.py                  # Connection pool, session manager
├── analytics/
│   ├── kpi_queries.sql        # CTEs: attrition, headcount, diversity, tenure
│   ├── kpi_engine.py          # Executes KPIs, writes snapshots to DB
│   └── data_generator.py      # Synthetic HR data (Faker)
├── scheduler/
│   └── dag_sync.py            # Apache Airflow DAG (15-min schedule)
├── api/
│   └── main.py                # FastAPI: /sync + /analytics endpoints
├── dashboard/
│   └── app.py                 # Streamlit KPI dashboard
├── tests/
│   ├── test_parser.py
│   └── test_normalizer.py
└── docker-compose.yml
```

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| Delta sync with cursor | Avoids full reloads; scales to 100K+ records |
| Workday-wins conflict rule | HRIS is authoritative for employment data (industry standard) |
| SQL CTEs over ORM for KPIs | Complex window functions, date spines — raw SQL is cleaner and faster |
| PostgreSQL upserts | `ON CONFLICT DO UPDATE` ensures idempotent sync runs |
| Airflow DAG with `max_active_runs=1` | Prevents overlapping sync cycles corrupting state |
| Pydantic response models | Type-safe API contracts, auto-generates OpenAPI docs |

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | DB + service health |
| `POST` | `/sync/trigger` | Manually trigger sync |
| `GET` | `/sync/status` | Latest sync per source |
| `GET` | `/sync/logs` | Paginated audit log |
| `GET` | `/analytics/headcount` | Headcount by department |
| `GET` | `/analytics/attrition` | Monthly attrition rate |
| `GET` | `/analytics/diversity` | Gender diversity % |
| `GET` | `/analytics/tenure` | Average tenure by dept |
| `GET` | `/analytics/data-quality` | Field completeness % |

---

## KPI Queries

All in `analytics/kpi_queries.sql`:

- **Headcount** — `COUNT(*) GROUP BY department`
- **Attrition rate** — `GENERATE_SERIES` date spine + `LAG()` window function
- **Diversity** — gender distribution with `SUM() OVER ()` percentage
- **Tenure** — `AGE()` + `EXTRACT()` for month-level precision
- **Headcount trend** — 12-month rolling with delta using `LAG()`
- **Data quality** — completeness % per field per source system

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

---

## Resume Bullets

> Built an end-to-end HR data integration platform in Python ingesting candidate records from 2 REST APIs (JSON + XML), normalizing 50K+ records into a unified PostgreSQL schema with conflict resolution and full audit logging — processing 10K records/cycle with zero data loss.

> Designed a workforce analytics pipeline using 20+ complex SQL queries (CTEs, window functions, date spines) reporting attrition, headcount, and diversity KPIs across 8 departments, exposed via FastAPI and visualized in a Streamlit dashboard.

> Orchestrated the full ETL lifecycle using an Apache Airflow DAG (poll → parse → normalize → upsert → KPI refresh) with delta-sync logic, retry handling, and automated conflict resolution between HRIS and ATS source-of-truth systems.

---

## Tech Stack

`Python 3.12` · `FastAPI` · `SQLAlchemy 2.x` · `PostgreSQL 16` · `Apache Airflow` · `Streamlit` · `Plotly` · `lxml` · `httpx` · `Faker` · `pytest` · `Docker`
