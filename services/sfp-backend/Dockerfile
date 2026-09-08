# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /sfp-backend ./cmd/sfp-backend

# Runtime
FROM alpine:3.20
RUN apk add --no-cache ca-certificates wget
WORKDIR /app
COPY --from=builder /sfp-backend /app/sfp-backend
ENV LISTEN_ADDR=:9099
EXPOSE 9099
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=10s \
  CMD wget -q --spider http://127.0.0.1:9099/health || exit 1
USER nobody
ENTRYPOINT ["/app/sfp-backend"]
