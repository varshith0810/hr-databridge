# HR DataBridge

**ATS Integration Middleware + Workforce Analytics Platform**

Full-stack project: Python/FastAPI backend + React frontend, deployed on Render.

---

## Structure

```
hr-databridge/
├── backend/                  ← Python FastAPI app
│   ├── ingestion/            ← API polling, parsing, normalization
│   ├── storage/              ← SQLAlchemy models, DB connection
│   ├── analytics/            ← SQL KPI queries + engine
│   ├── scheduler/            ← Airflow DAG
│   ├── api/main.py           ← FastAPI entrypoint
│   ├── tests/
│   └── requirements.txt
│
├── frontend/                 ← React + Vite app
│   ├── src/
│   │   ├── pages/            ← Overview, SyncStatus, Headcount, Attrition, Diversity, DataQuality
│   │   ├── components/       ← Sidebar, shared UI
│   │   └── utils/            ← api.js, useData.js
│   ├── package.json
│   └── vite.config.js
│
├── render.yaml               ← Render deployment (both services)
└── docker-compose.yml        ← Local dev
```

---

## Local development

```bash
# 1. Backend
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn api.main:app --reload
# API at http://localhost:8000/docs

# 2. Frontend (separate terminal)
cd frontend
npm install
npm run dev
# UI at http://localhost:5173
```

Or run everything with Docker:
```bash
docker-compose up --build
```

---

## Deploy to Render

1. Push repo to GitHub
2. Go to render.com → New → Blueprint
3. Connect your repo — Render reads `render.yaml` and creates all 3 services automatically
4. Done — live URLs in ~5 minutes

Live URLs after deploy:
- Frontend:  `https://hr-databridge-frontend.onrender.com`
- API docs:  `https://hr-databridge-api.onrender.com/docs`

---

## Tech stack

`Python 3.12` · `FastAPI` · `SQLAlchemy` · `PostgreSQL` · `React 18` · `Vite` · `Recharts` · `Docker` · `Render`
