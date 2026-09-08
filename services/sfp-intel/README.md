# sfp-intel (Go)

Go orchestration service for portal **sentiment** and **AI** HTTP paths. LLM inference stays on the existing OpenAI-compatible gateway (`ai_models.base_url` + encrypted `api_key`); this service does not embed models.

## Routes (native Go)

| Prefix | Notes |
|--------|-------|
| `GET /health` | Liveness |
| `POST /sentiment/ingest/x_monitor` | `X-Ingest-Token` auth; url MD5 idempotency |
| `GET /sentiment/news/list` | Paginated news |
| `DELETE /sentiment/news/{ids}` | Delete by comma-separated IDs |
| `POST /sentiment/news/collect` | Enqueue `sentiment_collect` → Redis `sfp:job:queue:llm` |
| `GET /sentiment/stats` | Dashboard counters + latest analysis |
| `GET /sentiment/analysis/list` | Paginated analysis history |
| `GET /sentiment/analysis/trend` | Trend chart (`limit`, default 24) |
| `POST /sentiment/analysis/run` | Enqueue `sentiment_analyze` |
| `GET /sentiment/analysis/{id}` | Analysis detail |
| `GET/PUT /sentiment/config` | Business config + merged AI model readout |

JWT + Redis session + RBAC match Python `PreAuthDependency` / `UserInterfaceAuthDependency`.

## Deferred to Python (`sentiment-intel` via proxy)

All `/ai/*` requests are **reverse-proxied** to `PYTHON_INTEL_URL` (default `http://sentiment-intel:9099`). This keeps heavy paths unchanged while sentiment orchestration moves to Go:

- `POST /ai/chat/send` — SSE streaming (Agno)
- `POST /ai/chat/consultant`, `/ai/chat/oneshot`
- `/ai/chat/session/*`, `/ai/chat/config`, `/ai/chat/cancel`
- `/ai/req/*` — requirements room bots
- `/ai/model` CRUD (admin writes + cache eviction)

`/open/*` remains on Python via nginx (not routed through sfp-intel).

LLM **job bodies** (`sentiment_collect`, `sentiment_analyze`, …) still execute in Python via `sfp-notify-worker` delegate until a follow-up worker migration lands. Go owns HTTP enqueue + ingest + read orchestration.

## Env

Same patterns as `market-read`:

- `JWT_SECRET_KEY`, `DB_*`, `REDIS_*`, `CREDENTIAL_ENCRYPTION_KEY`
- `SFP_X_MONITOR_INGEST_TOKEN` — required for X监测器 ingest
- `PYTHON_INTEL_URL` — AI proxy upstream (rollback target)

## Rollback (Python intel)

Slim nginx ships with Go routes by default. To revert sentiment/ai to Python only:

1. In `ruoyi-fastapi-frontend/bin/nginx.dockersentiment.slim.conf`, change `sfp-intel:8080` back to `sentiment-intel:9099` for `/prod-api/sentiment/` and `/prod-api/ai/`.
2. `docker compose … exec sentiment-frontend nginx -s reload`
3. Optional: stop `sfp-intel` container to free ~256m.

Or apply overlay `docker-compose.sentiment.intel-python-fallback.yml` (documents profile; nginx edit still required).

## Local test

```bash
cd services/sfp-intel
go test ./...
go build -o /tmp/sfp-intel ./cmd/sfp-intel
```
