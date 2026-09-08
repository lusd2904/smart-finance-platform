# sfp-backend rollout (Go platform API)

Go service at `services/sfp-backend` replaces Python `sentiment-backend` (`APP_MODULE=platform`) for portal auth, RBAC, job progress WS, open sync, and internal job routing.

## Implemented in Go (nginx → `sfp-backend:9099`)

| Path | Notes |
|------|--------|
| `GET /health` | Health probe |
| `GET /captchaImage` | Math captcha + Redis `captcha_codes:{uuid}` |
| `POST /login` | Form login, JWT + Redis session (same env keys as Python) |
| `GET /getInfo` | Permissions, roles, user payload (top-level fields) |
| `GET /getRouters` | Vue router tree (`data` array) |
| `POST /logout` | Clears Redis session |
| `/system/user/*` | List/detail/CRUD, resetPwd, changeStatus, deptTree, authRole |
| `/system/menu/*` | List/detail/CRUD, treeselect, roleMenuTreeselect |
| `/system/role/*` | List/detail/CRUD, changeStatus, dataScope, deptTree, authUser/* |
| `WS /ws/jobs` | Scheduler heartbeat + queue depth (Redis `sfp:scheduler:heartbeat`) |
| `POST /open/sync/token` | Admin sync JWT (transport crypto when enabled) |
| `POST /open/sync/pull` | Allowlisted MySQL + Influx paging |
| `POST /internal/jobs/run` | Routes LLM jobs → `sentiment-intel`, quant jobs → `sentiment-data` |

JWT/Redis contract matches `services/market-read/internal/auth` and Python `LoginService`.

## Slim stack: `sentiment-backend` optional

Default slim compose (`docker-compose.sentiment.slim.yml`) **does not start** `sentiment-backend`.
Workers use `INTERNAL_JOBS_URL=http://sfp-backend:9099/internal/jobs/run` (not Python platform).

Emergency Python platform fallback:

```bash
docker compose -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.platform-python-fallback.yml \
  --profile python-platform-fallback up -d sentiment-backend
```

Then revert nginx `ws/jobs` + `open/sync` to `sentiment-backend:9099`.

## Catch-all fall-through (still 404 until migrated)

| Prefix | Module | Notes |
|--------|--------|--------|
| `/dashboard/*` | `module_dashboard` | Home summary widgets |
| `/analysis/*` | `module_analysis` | Scheduler/analysis APIs |
| `/system/dept/*` | `module_admin` | Dept CRUD |
| `/system/dict/*` | `module_admin` | Dict type/data |
| `/system/config/*` | `module_admin` | Parameter config |
| `/common/*` | `module_admin` | Upload, guide, download |
| `/transport/crypto/*` | `module_admin` | Transport crypto handshake |
| `/app/*` | `module_admin` | App version |
| `/register` | `module_admin` | User registration |

Sibling services own `/trade/*`, `/market/*`, `/quant/*`, `/sentiment/*`, `/ai/*`, `/open/*` (except `/open/sync`).

## cursor-1 slim cutover (`--no-deps`)

```bash
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps --build sfp-backend

docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps sentiment-frontend
```

Verify:

```bash
curl -fsS http://127.0.0.1:19099/health
curl -fsS http://127.0.0.1:12580/prod-api/captchaImage | head -c 200
docker logs sfp-backend --tail 30
```

## Env (same as Python + job routing)

- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `JWT_REDIS_EXPIRE_MINUTES`
- `APP_SAME_TIME_LOGIN`
- `DB_*`, `REDIS_*`, `DB_PASSWORD`, `REDIS_PASSWORD`
- `INTERNAL_JOB_TOKEN`, `INTEL_JOBS_URL`, `QUANT_JOBS_URL`
- `INFLUX_*` (open sync `influx.daily` dataset)
- `TRANSPORT_CRYPTO_*` (open/sync encrypted transport)

## Tests

```bash
cd services/sfp-backend && go test ./...
```

CI job: `Go sfp-backend tests`.
