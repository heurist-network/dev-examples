### Tasks WebUI – Implementation Plan

Goal: Provide a small, secure WebUI to view (and optionally manage) scheduled tasks stored in SQLite (or JSON) and running via APScheduler.

### Scope

- **MVP (read-only)**: List and inspect tasks across conversations; filter/sort/search; view next/last run and timezone info.
- **Admin (optional)**: Run task now, enable/disable, delete, edit cron/timezone/name, view/set conversation default timezone.
- **Security**: Disabled by default; opt-in via env; token-based auth.

### Architecture

- **Backend**: FastAPI app served with Uvicorn (async, aligns with `aiosqlite` and current async stack).
- **Views**: Minimal server-rendered UI using Jinja2 + HTMX for progressive enhancement (no heavy SPA).
- **Data access**: Reuse existing async store and scheduler:
  - `src/tasks/store.py` → `list_tasks`, `get`, `update`, `remove`, `get_default_timezone`, `set_default_timezone`
  - `src/tasks/scheduler.py` → `get_task_scheduler()`, `run_now`, `update_task`, `remove_task`
- **Timezones**: Use `ZoneInfo` and per-conversation default where present; also display UTC. Optionally show browser-local via HTMX swapping or a tiny client-side helper.

### Process model

- The WebUI runs inside the same Python process (preferred) so it can call scheduler/store directly, minimizing duplication and preventing drift.
- It exposes read-only endpoints by default; mutating endpoints require explicit enable and token.
- If the scheduler is not started yet, the WebUI will lazily start it (safe to call `get_task_scheduler().start()` once).

### Files and placement

- `src/tasks/webui/app.py` – FastAPI app factory and routes
- `src/tasks/webui/templates/` – Jinja2 templates (`base.html`, `tasks.html`, `task_detail.html`)
- `src/tasks/webui/static/` – Minimal CSS (Tailwind CDN or small custom), htmx.js
- `src/tasks/webui/__init__.py` – app export
- Bootstrapping: optional CLI entry `python -m src.tasks.webui.app` or integrate `main.py` flag

### Configuration (env)

- `TASKS_WEBUI_ENABLED` = `true` | `false` (default `false`)
- `TASKS_WEBUI_HOST` (default `127.0.0.1`)
- `TASKS_WEBUI_PORT` (default `8789`)
- `TASKS_WEBUI_BASE_PATH` (default `/`) – for reverse proxy mounting
- `TASKS_WEBUI_ADMIN_TOKEN` – enables admin endpoints when set; required for mutations
- `TASKS_WEBUI_READONLY` = `true` | `false` (default `true` unless token provided)

### Data model displayed

- From `scheduled_tasks`:
  - id, name, prompt (truncated), cron, timezone, conversation_id, enabled, last_run_at, next_run_at, created_at, updated_at
- From prefs `scheduled_task_prefs`:
  - conversation_id, timezone, updated_at

### Endpoints

- Pages
  - `GET /` → Dashboard: stats (counts), links
  - `GET /tasks` → Paginated list; filters: `conversation_id`, `enabled`, text search (name/prompt/cron)
  - `GET /tasks/{task_id}` → Detail view (full prompt, meta, next run UTC/local)

- API (JSON)
  - `GET /api/tasks` → List with same filters; supports `page`, `page_size`, `sort`
  - `GET /api/tasks/{task_id}` → Task JSON
  - `POST /api/tasks/{task_id}/run` → Run now (admin only)
  - `POST /api/tasks/{task_id}/toggle` body: `{ enabled: bool }` (admin only)
  - `DELETE /api/tasks/{task_id}` (admin only)
  - `PUT /api/tasks/{task_id}` body: partial update `{ name?, cron?, timezone? }` (admin only)
  - `GET /api/prefs/{conversation_id}` → default timezone
  - `POST /api/prefs/{conversation_id}` body: `{ timezone: str }` (admin only)
  - `GET /api/meta/stats` → counts by enabled state, by conversation, upcoming runs

### Authentication and security

- If `TASKS_WEBUI_ADMIN_TOKEN` is set, admin endpoints require header `X-Admin-Token: <token>`.
- If not set, the API serves only read-only endpoints; UI hides action buttons.
- CORS disabled by default; UI and API share origin.
- When deployed, recommend placing behind a reverse proxy with mTLS or basic auth for extra protection.

### UI interactions (HTMX-driven)

- Tasks table: columns: Name, Cron, Timezone, Enabled, Last Run, Next Run (UTC), Next Run (Local), Conversation, Actions
- Filters: text search, enabled dropdown, conversation id select (auto-populated from data)
- Actions (admin): toggling enabled, run-now, delete, edit inline (cron/timezone/name) → in-row htmx forms
- Detail: show full prompt, meta JSON, computed next run using APScheduler (if needed for precision), and a compact run history area in future

### Pagination and performance

- Default `page_size=50`, server-side pagination and sorting
- SQL queries are simple and indexed; existing indexes on `conversation_id` and `enabled` suffice
- For JSON backend, filtering/pagination handled in Python (acceptable for small data; warn if large)

### Error handling and edge cases

- Safe conversions for `next_run_at` (may be `NULL`); display "—" when absent
- Timezone conversions wrapped in try/except; fall back to UTC
- Scheduler job might not exist for disabled tasks; UI accounts for it
- Concurrent updates: last-writer-wins via calls to `update_task`; on write failures, show inline error

### Implementation steps

1) Backend skeleton
- Create FastAPI app with lifespan: on start, ensure `get_task_scheduler().start()`
- Mount templates/static; set base path

2) Read-only pages and APIs
- `/tasks` page: list with filters and pagination; call `store.list_tasks(...)`
- `/api/tasks` and `/api/tasks/{id}` endpoints for JSON

3) Admin APIs and actions (guarded)
- Implement `run-now`, `toggle`, `delete`, and `update`
- Wire to `scheduler.run_now`, `scheduler.update_task`, `scheduler.remove_task`
- Use `tools.canonicalize_timezone` and `CronTrigger.from_crontab` to validate edits

4) UI enhancements
- Add HTMX endpoints for inline actions (partial renders)
- Add detail page with full prompt and meta
- Display local time using server-side conversion; optionally add a client-side toggle to browser-local

5) Security
- Middleware/dep that checks `X-Admin-Token` for mutating routes
- Hide admin controls in templates when read-only

6) Config and launchers
- Add CLI: `python -m src.tasks.webui.app` reading env; or `uv run src/tasks/webui/app.py`
- Optional: integrate with `main.py` via `TASKS_WEBUI_ENABLED=true` to spawn Uvicorn in background

7) Tests
- Unit tests using `httpx.AsyncClient` for API responses
- Validate filtering, pagination, and security checks
- Use temporary SQLite file; seed tasks; assert scheduler interactions via a light stub/mocking where necessary

### Example code snippets

Minimal app factory (pseudocode):

```python
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.tasks import store
from src.tasks.scheduler import get_task_scheduler

def create_app() -> FastAPI:
    app = FastAPI()

    @app.on_event("startup")
    async def startup():
        await get_task_scheduler().start()

    templates = Jinja2Templates(directory="src/tasks/webui/templates")
    app.mount("/static", StaticFiles(directory="src/tasks/webui/static"), name="static")

    @app.get("/tasks", response_class=HTMLResponse)
    async def tasks_page(request: Request, conversation_id: str | None = None, enabled: bool | None = None):
        tasks = await store.list_tasks(conversation_id)
        if enabled is not None:
            tasks = [t for t in tasks if t.enabled == enabled]
        return templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks})

    return app
```

### Rollout strategy

- Phase 1: Read-only UI + JSON list APIs
- Phase 2: Admin actions behind token
- Phase 3: Inline edits, timezone prefs management, and small run history (optional future table)

### Risks and mitigations

- Running multiple schedulers: use global `get_task_scheduler()` and idempotent `start()`
- DB locks: prefer read-only access in UI operations; mutate through scheduler APIs to keep consistency
- Timezones: ambiguous inputs handled via existing canonicalization; validate on update

### Operational notes

- Default bind is `127.0.0.1:8789`; reverse proxy if exposing externally
- Keep token out of logs; pass via env `TASKS_WEBUI_ADMIN_TOKEN`
- For JSON backend, performance will degrade with many tasks; document recommendation to use SQLite


