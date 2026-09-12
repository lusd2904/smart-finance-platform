module github.com/lusd2904/smart-finance-platform/services/sfp-backend

go 1.22

require (
	github.com/alicebob/miniredis/v2 v2.33.0
	github.com/go-sql-driver/mysql v1.8.1
	github.com/golang-jwt/jwt/v5 v5.2.1
	github.com/google/uuid v1.6.0
	github.com/gorilla/websocket v1.5.3
	github.com/lusd2904/smart-finance-platform/services/klineread v0.0.0
	github.com/redis/go-redis/v9 v9.6.1
	golang.org/x/crypto v0.31.0
)

replace github.com/lusd2904/smart-finance-platform/services/klineread => ../klineread

require (
	filippo.io/edwards25519 v1.1.0 // indirect
	github.com/alicebob/gopher-json v0.0.0-20200520072559-a9ecdc9d1d3a // indirect
	github.com/cespare/xxhash/v2 v2.2.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/yuin/gopher-lua v1.1.1 // indirect
)
