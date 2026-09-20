# Build stage
FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY services/klineread/go.mod services/klineread/go.sum* /src/services/klineread/
COPY services/market-read/go.mod services/market-read/go.sum* /src/services/market-read/
COPY services/trade-exec/go.mod services/trade-exec/go.sum* /src/services/trade-exec/
COPY services/data-api/go.mod services/data-api/go.sum* /src/services/data-api/
WORKDIR /src/services/data-api
RUN go mod download
COPY services/klineread /src/services/klineread
COPY services/market-read /src/services/market-read
COPY services/trade-exec /src/services/trade-exec
COPY services/data-api /src/services/data-api
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /data-api ./cmd/data-api

# Runtime
FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=builder /data-api /app/data-api
ENV LISTEN_ADDR=:8081
EXPOSE 8081
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=10s \
  CMD wget -q --spider http://127.0.0.1:8081/health || exit 1
USER nobody
ENTRYPOINT ["/app/data-api"]
