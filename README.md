# Singapore weather sentiment (Django)

Local Django app that ingests recent **X (Twitter)** posts for a **configurable Singapore–weather search**, classifies each new post with an **OpenAI** chat model into an integer **sentiment score 0–9** (0 unhappy, 4 neutral, 9 extremely happy), and shows a **dashboard** with **two bar charts** (rolling **1 hour** and **24 hours**) of score counts. Data is stored in **SQLite**.

## Time windows (dashboard)

On each page load, charts include posts whose **`analyzed_at`** timestamp falls in:

- **Last 1 hour:** `[now − 1h, now]`
- **Last 24 hours:** `[now − 24h, now]`

`now` uses Django’s configured **`TIME_ZONE`** (default **`Asia/Singapore`** via `DJANGO_TIME_ZONE`). Only rows with a non-null **`sentiment_score`** are counted.

## Prerequisites

- Python 3.11+
- **X API v2** access with **Recent search** (Bearer token).
- **OpenAI API** key with access to the model you set in `OPENAI_MODEL` (e.g. `gpt-4o-mini`).

## Setup

```powershell
cd d:\TPProjects\P2ATestProj1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set OPENAI_API_KEY, X_BEARER_TOKEN, and optional X_SEARCH_QUERY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open **http://127.0.0.1:8000/** for the dashboard and **http://127.0.0.1:8000/admin/** for admin.

## Ingestion (manual and cron)

One run fetches from X (incremental via stored **`since_id`**), **inserts only new** `platform_post_id` rows, then calls OpenAI for rows **without** a sentiment score (unless `--force-reanalyze`).

```powershell
.\.venv\Scripts\python.exe manage.py ingest_posts
```

Options:

- `--fetch-only` — X fetch + DB upsert only; no OpenAI.
- `--force-reanalyze` — classify **every** stored post again.
- `--verbose` — print each new post id.

### Hourly schedule

Run `ingest_posts` every hour with OS scheduling:

- **Linux/macOS (cron):** `0 * * * * cd /path/to/P2ATestProj1 && .venv/bin/python manage.py ingest_posts >> ingest.log 2>&1`
- **Windows (Task Scheduler):** Action = start `d:\TPProjects\P2ATestProj1\.venv\Scripts\python.exe`, arguments = `manage.py ingest_posts`, start in = `d:\TPProjects\P2ATestProj1`.

Ensure the task runs in an environment where `.env` is present or variables are set.

## Configuration (environment variables)

See **`.env.example`**. Important keys:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Model name (default `gpt-4o-mini`) |
| `X_BEARER_TOKEN` | X API Bearer token |
| `X_SEARCH_QUERY` | Recent-search query string |
| `INGEST_MAX_RESULTS` | Per-page tweet count (10–100; default 50) |
| `INGEST_MAX_PAGES` | Max pagination pages per run (default 2) |
| `INGEST_INTERVAL_MINUTES` | Documented cadence for schedulers (default 60); set your cron/Task Scheduler to match |
| `API_MAX_RETRIES` / `API_RETRY_BASE_SECONDS` | Backoff for X / OpenAI transient errors and rate limits |

## Failure handling

- **X:** HTTP **429** and **5xx** are retried with exponential backoff (see `tracker/services/retry.py`). Failures surface as `CommandError` on ingest.
- **OpenAI:** **Rate limits**, **timeouts**, **connection errors**, and **5xx** are retried the same way. Per-post failures store a short message in **`SocialPost.analysis_error`** and do not block other posts.

## Project layout

- `tracker/models.py` — `SocialPost`, `IngestCursor`
- `tracker/services/twitter_client.py` — X recent search
- `tracker/services/sentiment.py` — OpenAI JSON sentiment
- `tracker/management/commands/ingest_posts.py` — CLI ingest + classify
- `templates/tracker/dashboard.html` — Chart.js bar charts

## Tests

```powershell
python manage.py test tracker
```
