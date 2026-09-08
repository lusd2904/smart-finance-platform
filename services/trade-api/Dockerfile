# Build stage
FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY services/trade-exec /src/services/trade-exec
COPY services/trade-api /src/services/trade-api
WORKDIR /src/services/trade-api
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /trade-api ./cmd/trade-api

# Runtime
FROM alpine:3.20
RUN apk add --no-cache ca-certificates wget
WORKDIR /app
COPY --from=builder /trade-api /app/trade-api
ENV LISTEN_ADDR=:8080
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=10s \
  CMD wget -q --spider http://127.0.0.1:8080/health || exit 1
USER nobody
ENTRYPOINT ["/app/trade-api"]
