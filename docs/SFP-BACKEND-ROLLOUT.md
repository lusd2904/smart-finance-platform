# sfp-backend rollout (Go platform API)

Go service at `services/sfp-backend` replaces Python `sentiment-backend` (`APP_MODULE=platform`) for portal auth and RBAC HTTP.

## Implemented in Go (nginx catch-all → `sfp-backend:9099`)

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

JWT/Redis contract matches `services/market-read/internal/auth` and Python `LoginService`.

## Still on Python (`sentiment-backend:9099`)

Nginx **explicit** locations (not catch-all):

| Path | Owner | Reason |
|------|--------|--------|
| `/ws/jobs` | `sentiment-backend` | WebSocket job progress |
| `/open/sync/*` | `sentiment-backend` | Open sync token/pull (`module_admin`) |

Catch-all fall-through (until migrated):

| Prefix | Module | Notes |
|--------|--------|--------|
| `/dashboard/*` | `module_dashboard` | Home summary widgets |
| `/analysis/*` | `module_analysis` | Scheduler/analysis APIs |
| `/monitor/*` | `module_admin` | Server/cache/online monitor |
| `/system/dept/*` | `module_admin` | Dept CRUD (not in Go yet) |
| `/system/dict/*` | `module_admin` | Dict type/data |
| `/system/config/*` | `module_admin` | Parameter config |
| `/system/post/*` | `module_admin` | Post CRUD |
| `/system/notice/*` | `module_admin` | Notice board |
| `/common/*` | `module_admin` | Upload, guide, download |
| `/transport/crypto/*` | `module_admin` | Transport crypto handshake |
| `/app/*` | `module_admin` | App version |
| `/register` | `module_admin` | User registration |
| `/internal/jobs/*` | all Python API pods | Go workers delegate here |

Sibling agents own `/trade/*`, `/market/*`, `/quant/*`, `/sentiment/*`, `/ai/*`, `/open/*` (except `/open/sync`).

## cursor-1 slim cutover (`--no-deps`)

From repo root with env prepared (`SFP_DATA_ROOT`, `.env`, `.env.dockersentiment`):

```bash
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

# Build + start Go platform only (do not recreate Influx/MySQL)
docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps --build sfp-backend

# Reload frontend nginx (already mounts nginx.dockersentiment.slim.conf)
docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps sentiment-frontend
```

Verify:

```bash
curl -fsS http://127.0.0.1:12580/prod-api/captchaImage | head -c 200
# login → getInfo → getRouters with Admin-Token
curl -fsS http://127.0.0.1:12580/prod-api/health
docker logs sfp-backend --tail 30
```

## Rollback to Python platform HTTP

1. In `ruoyi-fastapi-frontend/bin/nginx.dockersentiment.slim.conf`, change catch-all:

   ```nginx
   location /docker-api/ { proxy_pass http://sentiment-backend:9099/; ... }
   location /prod-api/   { proxy_pass http://sentiment-backend:9099/; ... }
   ```

2. Reload frontend:

   ```bash
   docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml \
     up -d --no-deps sentiment-frontend
   ```

3. Optional: stop Go platform to free ~128m RSS:

   ```bash
   docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml \
     stop sfp-backend
   ```

`sentiment-backend` remains in slim stack for ws/jobs, open/sync, and worker `PYTHON_DELEGATE_URL`.

## Env (same as Python)

- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `JWT_REDIS_EXPIRE_MINUTES`
- `APP_SAME_TIME_LOGIN`
- `DB_*`, `REDIS_*`, `DB_PASSWORD`, `REDIS_PASSWORD`

## Tests

```bash
cd services/sfp-backend && go test ./...
```

CI job: `Go sfp-backend tests`.
