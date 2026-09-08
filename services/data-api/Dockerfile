# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /src/services/data-api
COPY services/data-api/go.mod services/data-api/go.sum ./
COPY services/market-read /src/services/market-read
RUN go mod download
COPY services/data-api .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /data-api ./cmd/data-api

# Runtime
FROM alpine:3.20
RUN apk add --no-cache ca-certificates wget
WORKDIR /app
COPY --from=builder /data-api /app/data-api
ENV LISTEN_ADDR=:8081
EXPOSE 8081
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=10s \
  CMD wget -q --spider http://127.0.0.1:8081/health || exit 1
USER nobody
ENTRYPOINT ["/app/data-api"]
