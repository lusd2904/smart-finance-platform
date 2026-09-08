# sfp-backend rollout (Go platform API)

Go service at `services/sfp-backend` is the platform API. Python `sentiment-backend` has been **deleted from main** ([PYTHON-REMOVED.md](./PYTHON-REMOVED.md)); do not apply the old `platform-python-fallback` overlay.

## Implemented in Go (nginx → `sfp-backend:9099`)

| Path | Notes |
|------|--------|
| `GET /health` | Health probe |
| `GET /captchaImage` | Math captcha + Redis `captcha_codes:{uuid}` |
| `POST /login` | Form login, JWT + Redis session (same env keys as Python) |
| `POST /register` | User self-registration when `sys.account.registerUser=true` |
| `GET /getInfo` | Permissions, roles, user payload (top-level fields) |
| `GET /getRouters` | Vue router tree (`data` array) |
| `POST /logout` | Clears Redis session |
| `/system/user/*` | List/detail/CRUD, resetPwd, changeStatus, deptTree, authRole |
| `/system/menu/*` | List/detail/CRUD, treeselect, roleMenuTreeselect |
| `/system/role/*` | List/detail/CRUD, changeStatus, dataScope, deptTree, authUser/* |
| `GET /system/dict/data/type/{dictType}` | Dict options for FE `useDict()` |
| `GET /system/config/configKey/{key}` | Config value in `msg` field (RuoYi contract) |
| `GET /dashboard/summary` | Workbench aggregation (Redis + MySQL blocks) |
| `/analysis/scheduler/*` | Job center overview, pause/resume, run-once, logs |
| `/common/upload`, `/common/guide/{module}` | Upload + embedded guides |
| `/common/download`, `/common/download/resource` | File download helpers |
| `/transport/crypto/frontend-config`, `/transport/crypto/public-key` | Transport crypto bootstrap |
| `WS /ws/jobs` | Scheduler heartbeat + queue depth (Redis `sfp:scheduler:heartbeat`) |
| `POST /open/sync/token` | Admin sync JWT (transport crypto when enabled) |
| `POST /open/sync/pull` | Allowlisted MySQL + Influx paging |
| `POST /internal/jobs/run` | Native Go jobs → Redis queues; `strategy_evaluate` → optional `STRATEGY_EVAL_URL` (legacy profile) |

JWT/Redis contract matches `services/market-read/internal/auth` and Python `LoginService`.

## `/internal/jobs/run` routing

| Job category | Handler |
|--------------|---------|
| Market + quant + LLM native jobs (`factor_scan`, `feishu_push`, `sentiment_analyze`, `req_send`, …) | Enqueue to `sfp:job:queue:{market\|quant\|llm}` for Go workers |
| `strategy_evaluate` (signal generation for Go trade path) | Optional bridge → `STRATEGY_EVAL_URL` (`quant-python-fallback` + `--profile legacy-python`) |

LLM job bodies run in `sfp-notify-worker` (no `INTEL_JOBS_URL` bridge). See `docs/LLM-NOTIFY-JOBS-NATIVE.md`.

Go workers consume Redis directly. `sfp-notify-worker` no longer calls `/internal/jobs/run`.

Emergency Python platform fallback:

```bash
docker compose -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.platform-python-fallback.yml \
  --profile legacy-python up -d sentiment-backend
```

## Tests

```bash
cd services/sfp-backend && go test ./...
```

CI job: `Go sfp-backend tests`.
