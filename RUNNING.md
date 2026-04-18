# Running RAGBuddy Locally

## Prerequisites

- Python 3.11+
- Node.js 20+
- An Anthropic API key (`sk-ant-...`)

---

## Backend Setup & Run

```bash
# 1. Go to the backend directory
cd O:/RAGBuddy/backend

# 2. Create a virtual environment (recommended)
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Create your .env file
copy ..\env.example .env        # Windows CMD
# or
cp ../.env.example .env         # PowerShell / bash

# 5. Edit .env — set your Anthropic API key (the only required field)
#    Open .env and set:  ANTHROPIC_API_KEY=sk-ant-your-key-here

# 6. Run the backend (development — auto-reloads on code changes)
uvicorn main:app --reload --port 8000

# ── What you should see in the terminal ───────────────────────────────────
# INFO:     Starting RAGBuddy API…
# INFO:     Database initialized.
# INFO:     SQLite KB table: 0 articles (no sync needed).
# INFO:     BM25 index not found — rebuilding from KB…
# INFO:     Models — structuring: claude-sonnet-4-6 (effort: medium) | ...
# INFO:     Uvicorn running on http://127.0.0.1:8000
# ─────────────────────────────────────────────────────────────────────────
```

### Verify the backend is running

```bash
# Health check
curl http://localhost:8000/api/health
# → {"status":"ok","kb_articles":0}

# Model config
curl http://localhost:8000/api/health/models
# → JSON showing all active model assignments

# Swagger UI — all endpoints documented
# Open in browser: http://localhost:8000/docs
```

---

## Frontend Setup & Run

```bash
# Open a second terminal

cd O:/RAGBuddy/frontend

# Install Node dependencies (first time only)
npm install

# Start the dev server (proxies /api/* to localhost:8000 automatically)
npm run dev

# → Open browser: http://localhost:5173
```

---

## Full Dev Flow (both running)

```
Terminal 1: backend   → http://localhost:8000
Terminal 2: frontend  → http://localhost:5173  (proxies API calls to backend)
```

---

## SQLite Database

The database file is created automatically at `backend/ragbuddy.db` on first run.

```bash
# Inspect the database (optional)
# Install sqlite3 CLI or use DB Browser for SQLite

sqlite3 backend/ragbuddy.db

# Useful queries:
.tables
# → documents  ingestion_history  kb_articles  kb_versions  query_history

SELECT title, category, version FROM kb_articles LIMIT 10;
SELECT filename, size_bytes, uploaded_at FROM documents;
SELECT question, latency_ms FROM query_history ORDER BY created_at DESC LIMIT 5;

# Check SQLite is using WAL mode (set automatically by the app):
PRAGMA journal_mode;
# → wal

.quit
```

### Reset the database

```bash
# Delete the DB file — it will be recreated (and re-synced from disk) on next startup
del backend\ragbuddy.db      # Windows CMD
rm backend/ragbuddy.db       # PowerShell / bash
```

---

## Production-style Run (no reload, all cores)

```bash
cd O:/RAGBuddy/backend

# Single worker (SQLite is single-writer; use 1 worker with SQLite)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

# With gunicorn (Linux/macOS — installs separately)
pip install gunicorn
gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

> **Note:** Keep `--workers 1` when using SQLite. SQLite supports concurrent readers
> (WAL mode) but only one writer at a time. For multi-worker deployments, switch to
> PostgreSQL by changing `DATABASE_URL` in `.env`:
> ```
> DATABASE_URL=postgresql+asyncpg://user:password@localhost/ragbuddy
> ```

---

## Docker (alternative)

```bash
# From the repo root
cd O:/RAGBuddy

# Build and start everything
docker-compose up --build

# Frontend → http://localhost:80
# Backend  → http://localhost:8000
```

---

## Common Issues

| Symptom | Fix |
|---|---|
| `ANTHROPIC_API_KEY not set` | Add `ANTHROPIC_API_KEY=sk-ant-...` to `backend/.env` |
| `ModuleNotFoundError: rank_bm25` | Run `pip install -r requirements.txt` inside the venv |
| `Address already in use :8000` | Kill the old process or use `--port 8001` |
| Frontend shows blank page | Make sure backend is running on port 8000 first |
| DB errors on startup | Delete `backend/ragbuddy.db` and restart — it rebuilds automatically |
