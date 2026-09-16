# Build with compose context: . (repo root). go.mod replace points at
# ../../services/klineread — a worker-only context cannot see that path,
# which left live images on the pre-#113 Flux client (lookup sentiment-influxdb).
FROM golang:1.24-alpine AS build
WORKDIR /src/workers/quant-worker
COPY workers/quant-worker/go.mod workers/quant-worker/go.sum ./
COPY services/klineread /src/services/klineread
RUN go mod download
COPY workers/quant-worker .
RUN CGO_ENABLED=0 go build -o /quant-worker ./cmd/quant-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=build /quant-worker /app/quant-worker
ENV WORKER_PORT=9097
EXPOSE 9097
CMD ["/app/quant-worker"]
