FROM golang:1.24-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /quant-worker ./cmd/quant-worker

FROM alpine:3.20
RUN apk add --no-cache ca-certificates wget
WORKDIR /app
COPY --from=build /quant-worker /app/quant-worker
ENV WORKER_PORT=9097
EXPOSE 9097
CMD ["/app/quant-worker"]
