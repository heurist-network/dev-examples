### Scheduled Tasks (src/tasks)

This module adds conversation-scoped scheduled tasks to the agent. It lets users schedule prompts (messages) to run automatically on cron schedules, execute them in the correct conversation context, and deliver results back via stdout (MVP) or XMTP (Phase 2).

### Core capabilities

- **Create tasks**: Persist a prompt, cron, timezone, and metadata per conversation.
- **List tasks**: Filter by conversation and enabled state; show next run in UTC and optionally local time.
- **Run now**: Execute a task immediately on-demand.
- **Enable/disable**: Toggle execution without deleting.
- **Delete tasks**: Remove from scheduler and storage.
- **Timezone prefs**: Per-conversation default timezone (SQLite backend).
- **Duplicate protection**: Exact and near-duplicate detection by schedule and prompt keywords.

### High-level architecture

- **`models.py`**: Defines `Task` dataclass (id, name, prompt, cron, timezone, conversation_id, created_by, enabled, last_run_at, next_run_at, meta).
- **`store.py`**: Storage facade selected by `TASKS_STORAGE_TYPE` (`sqlite` default, or JSON fallback). Exposes async CRUD and timezone-pref helpers.
- **`sqlite_store.py`**: SQLite backend using `aiosqlite`. Tables:
  - `scheduled_tasks` (task rows + `meta` JSON)
  - `scheduled_task_prefs` (conversation default timezone)
- **`scheduler.py`**: APScheduler `AsyncIOScheduler` wrapper that validates cron/timezones, schedules jobs, runs tasks, updates `last_run_at`/`next_run_at`, and notifies results.
- **`tools.py`**: Factory functions that create per-conversation agent function tools (create/list/delete/run-now/toggle/set-get-default-timezone) for the LLM runtime.
- **`notifiers.py`**: `StdoutNotifier` (MVP) and `XMTPNotifier` (Phase 2 via Node control server) to deliver results.

### Execution flow

1. App starts scheduler: `get_task_scheduler(...).start()` loads tasks from store and registers APScheduler jobs.
2. On trigger, `_run_task` pulls the `Task` from store and acquires a per-conversation lock to avoid concurrent runs in the same thread of conversation.
3. The agent manager is created/cached per conversation with task tools pre-bound and context flags set (`is_scheduled_execution`, `do_not_create_tasks`).
4. The prompt is wrapped with a header to prevent accidental task creation during execution, then processed by the agent manager.
5. Output and optional `trace_url` are sent via the configured notifier; `last_run_at` and `next_run_at` are updated and saved.

### Agent tools (per conversation)

- **`create_scheduled_task(prompt, cron, timezone?, name?, created_by?)`**
  - Validates timezone (canonicalizes abbreviations; handles ambiguous cases like `CST`, `IST`).
  - Validates cron via `CronTrigger.from_crontab` with timezone.
  - Prevents duplicates (exact and keyword-similar) on the same cron.
  - Enforces `MAX_TASKS_PER_CONVERSATION`.
  - Returns task summary including the computed next run.

- **`list_scheduled_tasks(enabled_only?)`**
  - Returns tasks for the conversation; includes UTC `nextRunUtc`. If a default timezone exists, also adds `nextRunLocal`.

- **`delete_scheduled_task(task_id)`**
  - Removes from scheduler and store; returns success message.

- **`run_task_now(task_id)`**
  - Ad-hoc execution with same delivery path and bookkeeping as scheduled runs.

- **`toggle_scheduled_task(task_id, enabled)`**
  - Enables/disables and re-schedules/un-schedules as needed.

- **`set_default_timezone(timezone)` / `get_default_timezone()`**
  - Stores/reads the conversation default timezone (SQLite only). JSON backend returns not-supported for prefs.

### Storage backends

- **SQLite (default)**
  - Set with `TASKS_STORAGE_TYPE=sqlite` (default).
  - DB path: `TASKS_DB_PATH` or fallback `SESSION_DB_PATH` (`data/sessions.db`).
  - Supports conversation timezone preferences and JSON `meta`.

- **JSON (compatibility)**
  - Set with `TASKS_STORAGE_TYPE=json` and optional `TASKS_STORE_PATH` (default `./data/tasks.json`).
  - No timezone preferences; `get/set_default_timezone` are no-ops.

- **Migration**
  - If `TASKS_MIGRATE_FROM_JSON=true` and a JSON store exists, tasks are migrated into SQLite on first access.

### Notifiers

- **Stdout (MVP)**: Pretty-prints execution results with timestamps.
- **XMTP (Phase 2)**: Sends results to the originating conversation through the Node control server.
  - `XMTP_CONTROL_URL` (default `http://127.0.0.1:8788/xmtp/send`)
  - `XMTP_CONTROL_TOKEN` (Bearer token)
  - Includes `trace_url` when `DEBUG_MODE=true`.

### Environment variables

- **Scheduling**
  - `SCHED_DEFAULT_TZ` (default `UTC`) – scheduler timezone when constructing the `AsyncIOScheduler`.
  - `MAX_TASKS_PER_CONVERSATION` (default `10`).

- **Storage**
  - `TASKS_STORAGE_TYPE` = `sqlite` | `json` (default `sqlite`).
  - `TASKS_DB_PATH` – path to SQLite DB. Fallback: `SESSION_DB_PATH` or `data/sessions.db`.
  - `TASKS_STORE_PATH` – JSON file path (JSON backend only).
  - `TASKS_MIGRATE_FROM_JSON` = `true` to migrate JSON → SQLite at startup.

- **XMTP notifier**
  - `XMTP_CONTROL_URL`, `XMTP_CONTROL_TOKEN`, `DEBUG_MODE`.

### Cron and timezone helpers

- Cron is validated using APScheduler `CronTrigger.from_crontab` with a timezone.
- Timezone canonicalization accepts common abbreviations/cities and maps to IANA (e.g., `PST` → `America/Los_Angeles`). Ambiguous inputs (e.g., `CST`, `IST`) return suggestions.
- Examples provided by `get_cron_examples()` and `get_timezone_examples()` in `tools.py`.

### Quick start (programmatic)

```python
from src.tasks.scheduler import get_task_scheduler
from src.tasks.models import Task
import asyncio

async def main():
    scheduler = get_task_scheduler(use_xmtp_notifier=False)  # True for XMTP delivery
    await scheduler.start()

    task = Task(
        id="my-task-id",
        name="Daily price check",
        prompt="Check BTC price and summarize market movers.",
        cron="0 9 * * *",  # 09:00 daily
        timezone="America/New_York",
        conversation_id="<conversation-id>",
        created_by="system",
        enabled=True,
    )
    await scheduler.add_task(task)

    # Optional: run now
    await scheduler.run_now(task.id)

asyncio.run(main())
```

### Quick start (agent tools)

The XMTP interface binds per-conversation tools from `src/tasks/tools.py`. From a conversation, the agent can call:

- Create: `create_scheduled_task(prompt, cron, timezone?, name?, created_by?)`
- List: `list_scheduled_tasks(enabled_only?)`
- Delete: `delete_scheduled_task(task_id)`
- Run now: `run_task_now(task_id)`
- Toggle: `toggle_scheduled_task(task_id, enabled)`
- Timezone: `set_default_timezone(timezone)`, `get_default_timezone()`

### Operational details and safeguards

- **Per-conversation locks**: Prevent concurrent runs within the same conversation.
- **Agent context flags**: `is_scheduled_execution` and `do_not_create_tasks` discourage the model from scheduling during an execution.
- **Misfire grace**: `misfire_grace_time=300` seconds on jobs.
- **Next run tracking**: Scheduler updates `next_run_at` from APScheduler after each run; `last_run_at` is recorded.
- **Error handling**: Errors are logged and a concise failure notification is attempted.

### Limitations and notes

- JSON backend does not support conversation timezone preferences.
- Duplicate detection is heuristic for near-duplicates (keyword overlap + same cron). Exact duplicates are blocked.
- Ensure the process has a single active scheduler instance (use `get_task_scheduler`).

### Testing

- See project tests (e.g., `test_tasks_unit.py`) for examples; run with your test runner (e.g., `pytest`).


