# Tasks WebUI

A web interface for viewing and managing scheduled tasks.

## Features

- **Dashboard**: Overview of task statistics and upcoming executions
- **Task List**: Browse, filter, and search all scheduled tasks
- **Task Details**: View full task information including prompt, schedule, and metadata
- **Admin Actions** (when enabled):
  - Run tasks immediately
  - Enable/disable tasks
  - Delete tasks
  - Update task properties

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Set environment variables

```bash
# Enable the WebUI
export TASKS_WEBUI_ENABLED=true

# For admin access (optional)
export TASKS_WEBUI_ADMIN_TOKEN="your-secret-token"

# Custom host/port (optional)
export TASKS_WEBUI_HOST="127.0.0.1"
export TASKS_WEBUI_PORT="8789"
```

### 3. Run the WebUI

```bash
# Using the launcher script
python run_webui.py

# Or directly
python -m src.tasks.webui.app
```

### 4. Access the interface

Open your browser to: http://127.0.0.1:8789

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `TASKS_WEBUI_ENABLED` | `false` | Enable the WebUI |
| `TASKS_WEBUI_HOST` | `127.0.0.1` | Bind host |
| `TASKS_WEBUI_PORT` | `8789` | Bind port |
| `TASKS_WEBUI_BASE_PATH` | `/` | Base path for reverse proxy |
| `TASKS_WEBUI_ADMIN_TOKEN` | (none) | Admin token for mutations |
| `TASKS_WEBUI_READONLY` | `true` | Force read-only mode |

## Security

By default, the WebUI runs in **read-only mode**. To enable admin actions:

1. Set `TASKS_WEBUI_ADMIN_TOKEN` environment variable
2. The UI will prompt for the token on first admin action
3. Token is stored in browser localStorage

⚠️ **Important**: 
- Never expose the WebUI to the internet without proper authentication
- Use a reverse proxy with HTTPS in production
- Keep the admin token secret

## API Endpoints

### Public (Read-Only)

- `GET /` - Dashboard page
- `GET /tasks` - Tasks list page
- `GET /tasks/{task_id}` - Task detail page
- `GET /api/tasks` - List tasks (JSON)
- `GET /api/tasks/{task_id}` - Get task (JSON)
- `GET /api/meta/stats` - Statistics (JSON)

### Admin (Requires Token)

- `POST /api/tasks/{task_id}/run` - Run task immediately
- `POST /api/tasks/{task_id}/toggle` - Enable/disable task
- `DELETE /api/tasks/{task_id}` - Delete task
- `PUT /api/tasks/{task_id}` - Update task properties

## Development

The WebUI is built with:
- **FastAPI** - Web framework
- **Jinja2** - Template engine
- **Tailwind CSS** - Styling (via CDN)
- **HTMX** - Dynamic interactions (minimal JavaScript)

Templates are in `src/tasks/webui/templates/`

## Troubleshooting

### WebUI won't start
- Check `TASKS_WEBUI_ENABLED=true` is set
- Verify port 8789 is available
- Check logs for startup errors

### Can't perform admin actions
- Ensure `TASKS_WEBUI_ADMIN_TOKEN` is set
- Check browser console for auth errors
- Verify token in localStorage matches environment

### Tasks not showing
- Verify database path is correct
- Check if scheduler is running
- Look for database connection errors in logs
