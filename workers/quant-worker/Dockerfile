# Build with compose context: . (repo root).
FROM golang:1.24-alpine AS build
WORKDIR /src
COPY services/klineread/go.mod services/klineread/go.sum* /src/services/klineread/
COPY workers/quant-worker/go.mod workers/quant-worker/go.sum* /src/workers/quant-worker/
WORKDIR /src/workers/quant-worker
RUN go mod download
COPY services/klineread /src/services/klineread
COPY workers/quant-worker /src/workers/quant-worker
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /quant-worker ./cmd/quant-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=build /quant-worker /app/quant-worker
ENV WORKER_PORT=9097
EXPOSE 9097
USER nobody
CMD ["/app/quant-worker"]
