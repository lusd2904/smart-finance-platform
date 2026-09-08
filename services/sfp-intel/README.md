# sfp-intel (Go)

Go orchestration service for portal **sentiment**, **AI chat**, **AI model admin**, **requirements board**, and **`/open/*`** HTTP paths. LLM inference uses the existing OpenAI-compatible gateway configured in MySQL `ai_models` (`base_url` + encrypted `api_key`); this service does not embed models.

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
| `POST /ai/chat/send` | NDJSON SSE stream to OpenAI-compatible gateway |
| `GET/PUT /ai/chat/config` | Per-user chat settings (`ai_chat_config`) |
| `GET /ai/chat/session/list` | Session list (`sfp_chat_session`) |
| `GET/DELETE /ai/chat/session/{id}` | Session detail / delete |
| `POST /ai/chat/cancel` | Cancel in-flight stream by `runId` |
| `POST /ai/chat/consultant` | Portfolio consultant (sync completion) |
| `POST /ai/chat/oneshot` | One-shot symbol analysis (sync completion) |
| `/ai/model/*` | Model CRUD (`ai_models`) |
| `/ai/req/*` | Requirements room + backlog (`ai_req_*`) |
| `POST /open/token` | External login → short-lived JWT |
| `GET /open/requirements` | External requirements export |

JWT + Redis session + RBAC match Python `PreAuthDependency` / `UserInterfaceAuthDependency`.

Chat sessions/messages persist in MySQL (`sfp_chat_session`, `sfp_chat_message`). Active runs are cancelled via an in-process registry keyed by `runId`.

LLM **job bodies** execute in **`sfp-notify-worker`** (Go). This service owns HTTP enqueue, streaming chat, and read orchestration. See `docs/LLM-NOTIFY-JOBS-NATIVE.md`.

## Env

Same patterns as `market-read`:

- `JWT_SECRET_KEY`, `DB_*`, `REDIS_*`, `CREDENTIAL_ENCRYPTION_KEY`
- `SFP_X_MONITOR_INGEST_TOKEN` — required for X监测器 ingest

## Rollback (Python intel)

Apply overlay `docker-compose.sentiment.intel-python-fallback.yml` with `--profile legacy-python` and swap nginx to `nginx.dockersentiment.slim.python-intel.conf` so `/sentiment/` + `/ai/` + `/open/` route to `sentiment-intel:9099` again. Default slim does not start Python intel.

## Local test

```bash
cd services/sfp-intel
go test ./...
go build -o /tmp/sfp-intel ./cmd/sfp-intel
```
