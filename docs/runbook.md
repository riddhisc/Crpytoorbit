# Runbook

## Deploy

`docker compose up --build` for a laptop. On Render, apply `render.yaml`. Set `DEMO_MODE=false` and `API_KEY` before anyone else can reach it. Point `DATABASE_URL` at Postgres if the data must survive a restart.

## Rotate the API key

Change `API_KEY` and restart. Write calls send `X-API-Key`. Compare is a SHA-256 digest compare so length differences do not short-circuit the check.

## Restore demo data

`POST /api/v1/reset` (demo mode, confirm in the UI by typing RESET) then `POST /api/v1/demo/load`, or `make demo`.

## Read logs

Logs are JSON on stdout: `request_id`, path, status, and `duration_ms`. Reconcile logs `parse_done`, `match_done`, `rules_done`.

## A failed import

Open Import issues or `GET /api/v1/import-issues`. The job row is `failed` with `error`. Re-upload after fixing the file. The same bytes will not duplicate rows.

## Readiness

`GET /health` is liveness. `GET /ready` checks the database and that Alembic is at `0001_initial`. `GET /metrics` is Prometheus text.
