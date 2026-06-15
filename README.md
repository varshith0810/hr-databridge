# HR DataBridge

ATS/HRIS integration middleware and workforce analytics demo with a FastAPI backend, PostgreSQL storage, and a React + Vite frontend.

## What you need to install

- **Python 3.12** for the FastAPI backend.
- **Node.js 20+ and npm** for the React/Vite frontend.
- **PostgreSQL 16** for local database storage, or **Docker Desktop / Docker Compose** if you prefer containers.
- Optional API tooling such as `curl`, Postman, or Insomnia for testing endpoints.

## Local development without Docker

### 1. Start PostgreSQL

Create a local database/user matching `.env.example`, or update `DATABASE_URL` in your shell/env file:

```bash
createdb hr_databridge
```

Default connection string:

```text
postgresql://hr_user:hr_pass@localhost:5432/hr_databridge
```

### 2. Run the backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd backend
uvicorn api.main:app --reload
```

Backend URLs:

- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs

### 3. Run the frontend in another terminal

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: http://localhost:5173

## Local development with Docker Compose

```bash
docker compose up --build
```

Docker Compose starts:

- PostgreSQL at `localhost:5432`
- FastAPI at http://localhost:8000
- React/Vite at http://localhost:5173

## Useful debug commands

```bash
pytest -q
cd frontend && npm run build
curl http://localhost:8000/health
```

## Project structure

```text
backend/                  FastAPI app, ingestion, storage, analytics, tests
frontend/                 React + Vite UI
requirements.txt          Python dependencies for local backend development
backend/requirements.txt  Python dependencies used by backend container/deploys
docker-compose.yml        Local PostgreSQL + API + frontend stack
```

## Main frameworks and libraries

- Backend: FastAPI, Uvicorn, SQLAlchemy, Pydantic, lxml, httpx, python-dotenv, pytest.
- Database: PostgreSQL.
- Frontend: React 18, Vite, React Router, Recharts, Axios.
- Container/devops: Docker Compose, Render configuration.
