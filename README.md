# AI Project Manager v2.0

A **production-grade AI DevOps assistant** that listens to GitHub webhooks, runs multi-language static analysis asynchronously, generates AI suggestions, applies automated fixes via PR, and presents everything through a real-time dashboard with auth.

```
GitHub Push/PR
     │
     ▼
POST /webhook/github      ← FastAPI (validates signature)
     │
     ▼
Job created in PostgreSQL ← status: pending
     │
     ▼
Celery Task queued        ← Redis broker
     │
     ▼
Worker: Clone → Analyze → AI Suggestions → Save Report
     │
     ▼
Dashboard (real-time polling) + GitHub Comment (optional)
     │
     ▼ (user triggers)
Auto-Fix Worker: Patch files → Create Branch → Open PR
```

---

## Architecture v2.0

```
ai-project-manager/
├── backend/
│   ├── main.py                    # [UPDATED] FastAPI app + lifespan + CORS
│   ├── database.py                # [NEW] SQLAlchemy engine, SessionLocal, Base
│   ├── webhook.py                 # Webhook signature validation + parsing
│   ├── auth/
│   │   ├── __init__.py
│   │   └── jwt.py                 # [NEW] JWT tokens, password hashing, auth deps
│   ├── models/
│   │   ├── __init__.py
│   │   ├── orm.py                 # [NEW] SQLAlchemy ORM: User, Report, Job
│   │   └── schemas.py             # [UPDATED] Pydantic schemas (auth, jobs added)
│   ├── api/                       # [NEW] Modular route files
│   │   ├── __init__.py
│   │   ├── auth.py                # POST /auth/signup|login, GET /auth/me
│   │   ├── webhook.py             # POST /webhook/github  → queues job
│   │   ├── reports.py             # GET/DELETE /reports, POST /reports/{id}/autofix
│   │   └── jobs.py                # GET /jobs, GET /jobs/{id}
│   ├── workers/                   # [NEW] Async task system
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery + Redis config, queue routing
│   │   └── tasks.py               # analyze_repository + apply_autofix tasks
│   ├── services/
│   │   ├── ai_service/            # LLM providers (unchanged)
│   │   │   ├── base.py
│   │   │   ├── factory.py
│   │   │   ├── groq_provider.py
│   │   │   ├── together_provider.py
│   │   │   ├── hf_provider.py
│   │   │   ├── nvidia_provider.py
│   │   │   └── ollama_provider.py
│   │   ├── analyzers/             # [NEW] Plugin-based multi-language analysis
│   │   │   ├── __init__.py
│   │   │   └── runner.py          # Flake8, Pylint, Bandit, ESLint, Hadolint
│   │   ├── autofix_service.py     # [NEW] Git patch → branch → PR via GitHub API
│   │   ├── github_service.py      # Commit comments
│   │   ├── report_service.py      # [UPDATED] PostgreSQL-backed report CRUD
│   │   └── suggestion_engine.py   # [UPDATED] Structured AI suggestions
│   └── utils/
│       ├── __init__.py
│       └── repo_processor.py      # Clone, checkout, cleanup
├── frontend/
│   ├── index.html                 # [UPDATED] Auth modal, jobs view, nav
│   ├── styles.css                 # [UPDATED] Full UI redesign
│   └── app.js                     # [UPDATED] Auth, filters, charts, job polling
├── alembic/                       # [NEW] Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
├── alembic.ini                    # [NEW]
├── docker-compose.yml             # [NEW] Full local stack
├── Dockerfile                     # [NEW]
├── render.yaml                    # [UPDATED] API + 2 workers + DB + Redis
├── requirements.txt               # [UPDATED]
├── .env.example                   # [UPDATED]
└── README.md
```

---

## What's New in v2.0

| Feature | Details |
|---|---|
| **Async Job Queue** | Redis + Celery — webhook returns instantly, analysis runs in background |
| **Job Status Tracking** | `pending → processing → done → failed` stored in PostgreSQL |
| **Auto-Fix PR** | AI suggestions applied to files, new branch created, PR opened automatically |
| **Multi-Language Analysis** | Python (flake8/pylint/bandit), JS/TS (eslint), Docker (hadolint) — plugin architecture |
| **PostgreSQL** | Full ORM with SQLAlchemy, Alembic migrations, JSON report storage |
| **JWT Auth** | Signup/login, per-user report isolation, GitHub token connection |
| **Advanced Dashboard** | Severity trend chart, filter pills, search, sort, job status polling |
| **Celery Flower** | Built-in worker monitoring UI at `:5555` |
| **Docker Compose** | One-command local stack: API + 2 workers + Postgres + Redis + Flower |

---

## Prerequisites

- Python 3.11+
- Redis (or Docker)
- PostgreSQL (or Docker; SQLite works for local dev)
- One LLM provider key (Groq free tier works great)
- Optional: GitHub token for comments and auto-fix

---

## Local Setup (Recommended: Docker Compose)

### Option A — Docker Compose (easiest)

```bash
git clone <this-repo>
cd ai-project-manager

cp .env.example .env
# Edit .env — at minimum set LLM_PROVIDER and GROQ_API_KEY

docker-compose up --build
```

Services started:
| Service | URL |
|---|---|
| API + Dashboard | http://localhost:8000 |
| Celery Flower | http://localhost:5555 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

### Option B — Manual Local Setup

#### 1. Install Redis

```bash
# macOS
brew install redis && brew services start redis

# Ubuntu/Debian
sudo apt install redis-server && sudo systemctl start redis

# Windows — use Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

#### 2. Install PostgreSQL (or skip for SQLite)

```bash
# macOS
brew install postgresql@16 && brew services start postgresql@16

# Ubuntu
sudo apt install postgresql && sudo systemctl start postgresql

# Create DB
psql -U postgres -c "CREATE USER ai_pm_user WITH PASSWORD 'localpassword';"
psql -U postgres -c "CREATE DATABASE ai_pm_db OWNER ai_pm_user;"
```

#### 3. Python environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://ai_pm_user:localpassword@localhost:5432/ai_pm_db
# Or for SQLite (no Postgres needed):
# DATABASE_URL=sqlite:///./ai_pm.db

REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=some-long-random-string-here
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

#### 5. Run database migrations

```bash
alembic upgrade head
```

#### 6. Start all services (4 terminals)

**Terminal 1 — API server:**
```bash
PYTHONPATH=. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Analysis worker:**
```bash
PYTHONPATH=. celery -A backend.workers.celery_app worker --loglevel=info -Q analysis -c 2
```

**Terminal 3 — Auto-fix worker:**
```bash
PYTHONPATH=. celery -A backend.workers.celery_app worker --loglevel=info -Q autofix -c 1
```

**Terminal 4 — Flower monitoring (optional):**
```bash
PYTHONPATH=. celery -A backend.workers.celery_app flower --port=5555
```

Open **http://localhost:8000** for the dashboard.
Open **http://localhost:5555** for Celery task monitoring.

---

## GitHub Webhook Setup

```bash
# Install ngrok for local development
brew install ngrok   # or download from ngrok.com

# Expose local server
ngrok http 8000
```

In your GitHub repo → **Settings → Webhooks → Add webhook:**
- **Payload URL:** `https://xxxx.ngrok.io/webhook/github`
- **Content type:** `application/json`
- **Secret:** value from `GITHUB_WEBHOOK_SECRET` in `.env`
- **Events:** ✅ Push events, ✅ Pull requests

---

## API Reference

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create account |
| POST | `/auth/login` | — | Get JWT token |
| GET | `/auth/me` | ✅ | Current user info |
| POST | `/auth/github/connect` | ✅ | Connect GitHub token |
| DELETE | `/auth/github/disconnect` | ✅ | Remove GitHub token |

### Reports
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/reports` | optional | List reports (filtered to user if auth'd) |
| GET | `/reports?severity_min=7` | optional | Filter by severity |
| GET | `/reports?repository=org/repo` | optional | Search by repo |
| GET | `/reports/trend?days=30` | optional | Severity trend data for chart |
| GET | `/reports/{id}` | optional | Full report with AI suggestions |
| POST | `/reports/{id}/autofix` | ✅ | Queue auto-fix PR job |
| DELETE | `/reports/{id}` | ✅ | Delete report |

### Jobs
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/jobs` | optional | List recent jobs |
| GET | `/jobs?status=processing` | optional | Filter by status |
| GET | `/jobs/{id}` | optional | Job detail + status |

### System
| Method | Path | Description |
|---|---|---|
| POST | `/webhook/github` | GitHub webhook receiver |
| GET | `/health` | Health check |
| GET | `/` | Dashboard UI |

---

## Simulating a Webhook (Local Testing)

```bash
curl -X POST http://localhost:8000/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{
    "repository": {
      "clone_url": "https://github.com/psf/requests.git",
      "full_name": "psf/requests"
    },
    "ref": "refs/heads/main",
    "after": "abc123def456",
    "head_commit": {"message": "fix: update auth"},
    "commits": [{"added": [], "modified": ["requests/api.py"], "removed": []}]
  }'
```

Response:
```json
{
  "status": "queued",
  "job_id": "uuid-here",
  "celery_task_id": "celery-uuid",
  "repository": "psf/requests",
  "commit": "abc123de"
}
```

Then poll: `GET /jobs/{job_id}` until `status == "done"`.

---

## Multi-Language Analysis

| Language | Tool | File Types |
|---|---|---|
| Python | flake8 | `.py` |
| Python | pylint | `.py` |
| Python | bandit | `.py` (security) |
| Python | pip-audit | `requirements.txt` |
| JavaScript | eslint | `.js`, `.jsx`, `.mjs` |
| TypeScript | eslint | `.ts`, `.tsx` |
| Docker | hadolint | `Dockerfile` |

### Adding a Custom Analyzer

Create a class in `backend/services/analyzers/runner.py`:

```python
class MyAnalyzer:
    name = "my-tool"
    supported_extensions = [".rb"]   # Ruby, for example

    def analyze(self, filepath: str, repo_root: str) -> List[Issue]:
        # Run your tool, return List[Issue]
        ...

# Register it:
ANALYZER_REGISTRY.append(MyAnalyzer())
```

That's it — the runner will pick it up automatically for matching files.

---

## Auto-Fix PR Flow

1. User clicks **⚡ AUTO-FIX PR** in dashboard (requires GitHub account connected)
2. `POST /reports/{id}/autofix` → queues `apply_autofix` Celery task
3. Worker reads AI `improved_code` from each issue
4. Patches files using bottom-up line replacement (safe, minimal diff)
5. Creates branch `ai-autofix/{commit-sha}`
6. Opens PR against the original branch
7. Dashboard shows PR link in report detail

**Safety note:** The PR description explicitly warns reviewers to validate AI changes before merging.

---

## Severity Scoring

| Issue Type | Points |
|---|---|
| security | 3.0 |
| error | 2.0 |
| dependency | 1.5 |
| warning | 0.5 |

Score is the sum of all issues, capped at 10.0.

---

## Deployment (Render)

The `render.yaml` defines:
- **API service** — FastAPI web server
- **worker-analysis** — Celery worker for the `analysis` queue
- **worker-autofix** — Celery worker for the `autofix` queue
- **PostgreSQL** database (free tier)

### Steps:

1. Push to GitHub
2. Connect repo in [Render dashboard](https://render.com)
3. Select **"Use render.yaml"** — it creates all services automatically
4. Add a **Redis** instance manually: New → Redis → link to services
5. Set secret env vars in Render dashboard:
   - `JWT_SECRET_KEY`
   - `GROQ_API_KEY` (or other LLM key)
   - `GITHUB_TOKEN`
   - `GITHUB_WEBHOOK_SECRET`
6. Update `vercel.json` with your Render API URL (if using Vercel for frontend)
7. Run migrations on first deploy:
   ```bash
   # In Render shell or one-off job:
   alembic upgrade head
   ```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | sqlite:///./ai_pm.db | PostgreSQL or SQLite connection string |
| `REDIS_URL` | Yes | redis://localhost:6379/0 | Redis connection for Celery |
| `JWT_SECRET_KEY` | Yes | dev-secret | Secret for signing JWT tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | 1440 | JWT expiry (24h default) |
| `LLM_PROVIDER` | Yes | groq | AI provider: groq/together/hf/nvidia/ollama |
| `GROQ_API_KEY` | If using Groq | — | Groq API key |
| `TOGETHER_API_KEY` | If using Together | — | Together AI key |
| `HF_API_KEY` | If using HF | — | HuggingFace API key |
| `NVIDIA_API_KEY` | If using NVIDIA | — | NVIDIA NIM key |
| `NVIDIA_MODEL` | No | meta/llama-3.1-8b-instruct | NVIDIA model |
| `OLLAMA_API_URL` | If using Ollama | http://localhost:11434/... | Ollama endpoint |
| `OLLAMA_MODEL` | No | llama3 | Ollama model name |
| `GITHUB_TOKEN` | For comments/autofix | — | GitHub personal access token |
| `GITHUB_WEBHOOK_SECRET` | Recommended | — | HMAC secret for webhook validation |
| `ENABLE_GH_COMMENTS` | No | false | Auto-post analysis as commit comment |
| `TEMP_DIR` | No | /tmp/ai_pm_repos | Temp directory for repo clones |
| `PYTHONPATH` | Yes | . | Must be set to project root |
