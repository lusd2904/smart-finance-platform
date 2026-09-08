# syntax=docker/dockerfile:1

FROM golang:1.22-alpine AS build
WORKDIR /src
RUN apk add --no-cache git ca-certificates
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/market-worker ./cmd/market-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=build /out/market-worker /app/market-worker
ENV WORKER_PORT=9098
EXPOSE 9098
HEALTHCHECK --interval=15s --timeout=5s --retries=12 --start-period=20s \
  CMD wget -q -O- http://127.0.0.1:9098/health >/dev/null || exit 1
USER nobody
ENTRYPOINT ["/app/market-worker"]
