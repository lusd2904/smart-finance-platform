module github.com/lusd2904/smart-finance-platform/workers/quant-worker

go 1.24.0

require (
	github.com/fernet/fernet-go v0.0.0-20240119011108-303da6aec611
	github.com/go-sql-driver/mysql v1.8.1
	github.com/google/uuid v1.6.0
	github.com/longbridge/openapi-go v0.27.0
	github.com/lusd2904/smart-finance-platform/services/klineread v0.0.0
	github.com/redis/go-redis/v9 v9.7.0
	github.com/shopspring/decimal v1.4.0
)

replace github.com/lusd2904/smart-finance-platform/services/klineread => ../../services/klineread

require (
	filippo.io/edwards25519 v1.1.0 // indirect
	github.com/Allenxuxu/ringbuffer v0.0.11 // indirect
	github.com/BurntSushi/toml v1.3.2 // indirect
	github.com/Netflix/go-env v0.0.0-20220526054621-78278af1949d // indirect
	github.com/cespare/xxhash/v2 v2.2.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/golang/protobuf v1.5.2 // indirect
	github.com/google/go-querystring v1.1.0 // indirect
	github.com/gorilla/websocket v1.5.0 // indirect
	github.com/jinzhu/copier v0.3.5 // indirect
	github.com/joho/godotenv v1.4.0 // indirect
	github.com/longbridge/openapi-protobufs/gen/go v0.7.0 // indirect
	github.com/longbridge/openapi-protocol/go v0.5.0 // indirect
	github.com/pkg/errors v0.9.1 // indirect
	golang.org/x/oauth2 v0.35.0 // indirect
	google.golang.org/protobuf v1.28.1 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)
