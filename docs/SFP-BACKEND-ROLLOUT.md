# sfp-backend rollout (Go platform API)

Go service at `services/sfp-backend` replaces Python `sentiment-backend` (`APP_MODULE=platform`) for portal auth, RBAC, dashboard, analysis scheduler UI, and internal job routing.

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
| `POST /internal/jobs/run` | Native Go jobs → Redis queues; LLM → `sentiment-intel`; `strategy_evaluate` → `sentiment-data` |

JWT/Redis contract matches `services/market-read/internal/auth` and Python `LoginService`.

## `/internal/jobs/run` routing

| Job category | Handler |
|--------------|---------|
| Market + quant native jobs (`factor_scan`, `market_heat_collect`, `feishu_push`, …) | Enqueue to `sfp:job:queue:{market\|quant\|llm}` for Go workers |
| LLM / Grok pipelines (`sentiment_collect`, `ai_analyze`, …) | **Temporary bridge** → `INTEL_JOBS_URL` (`sentiment-intel`) |
| `strategy_evaluate` (signal generation for Go trade path) | **Temporary bridge** → `QUANT_JOBS_URL` (`sentiment-data`) |

Go workers (`sfp-market-worker`, `sfp-quant-worker`, `sfp-notify-worker`) consume Redis directly; they only call `/internal/jobs/run` for the bridge types above.

## Slim stack: `sentiment-backend` optional

Default slim compose (`docker-compose.sentiment.slim.yml`) **does not start** `sentiment-backend`.
Workers use `INTERNAL_JOBS_URL=http://sfp-backend:9099/internal/jobs/run`.

Emergency Python platform fallback:

```bash
docker compose -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.platform-python-fallback.yml \
  --profile python-platform-fallback up -d sentiment-backend
```

## Tests

```bash
cd services/sfp-backend && go test ./...
```

CI job: `Go sfp-backend tests`.
