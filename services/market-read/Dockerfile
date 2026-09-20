# Build stage
FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY services/klineread/go.mod services/klineread/go.sum* /src/services/klineread/
COPY services/market-read/go.mod services/market-read/go.sum* /src/services/market-read/
WORKDIR /src/services/market-read
RUN go mod download
COPY services/klineread /src/services/klineread
COPY services/market-read /src/services/market-read
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /market-read ./cmd/market-read

# Runtime
FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=builder /market-read /app/market-read
ENV LISTEN_ADDR=:8080
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=10s \
  CMD wget -q --spider http://127.0.0.1:8080/health || exit 1
USER nobody
ENTRYPOINT ["/app/market-read"]
