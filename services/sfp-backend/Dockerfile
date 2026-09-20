# Build stage
FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY services/klineread/go.mod services/klineread/go.sum* /src/services/klineread/
COPY services/sfp-backend/go.mod services/sfp-backend/go.sum* /src/services/sfp-backend/
WORKDIR /src/services/sfp-backend
RUN go mod download
COPY services/klineread /src/services/klineread
COPY services/sfp-backend /src/services/sfp-backend
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /sfp-backend ./cmd/sfp-backend

# Runtime
FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=builder /sfp-backend /app/sfp-backend
ENV LISTEN_ADDR=:9099
EXPOSE 9099
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=10s \
  CMD wget -q --spider http://127.0.0.1:9099/health || exit 1
USER nobody
ENTRYPOINT ["/app/sfp-backend"]
