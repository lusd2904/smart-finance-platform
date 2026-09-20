FROM golang:1.24-alpine AS build
WORKDIR /src
COPY services/klineread/go.mod services/klineread/go.sum* /src/services/klineread/
COPY workers/notify-worker/go.mod workers/notify-worker/go.sum* /src/workers/notify-worker/
WORKDIR /src/workers/notify-worker
RUN go mod download
COPY services/klineread /src/services/klineread
COPY workers/notify-worker /src/workers/notify-worker
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /notify-worker ./cmd/notify-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=build /notify-worker /app/notify-worker
ENV WORKER_PORT=9096
EXPOSE 9096
USER nobody
CMD ["/app/notify-worker"]
