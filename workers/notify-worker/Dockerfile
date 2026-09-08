FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /notify-worker ./cmd/notify-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata wget
WORKDIR /app
COPY --from=build /notify-worker /app/notify-worker
ENV WORKER_PORT=9096
EXPOSE 9096
CMD ["/app/notify-worker"]
