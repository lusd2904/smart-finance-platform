# Go Quant Worker

Low-memory consumer for Redis `sfp:job:queue:quant`.

| Job type | Handler |
|----------|---------|
| `indicator_refresh` | Go native (Influx → MySQL snapshot + Redis readmodel) |
| other quant jobs | Delegates to Python `/internal/jobs/run` |

Health: `http://127.0.0.1:19096/health` (host) / `:9097/health` (compose).
