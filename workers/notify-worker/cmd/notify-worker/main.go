package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	mwcfg "github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/handler"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/store"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	cfg := mwcfg.Load()
	cfg.WorkerPort = 9096

	svc, err := store.NewService(cfg)
	if err != nil {
		logger.Error("mysql init failed", "err", err)
		os.Exit(1)
	}
	defer svc.Close()

	rdb := redis.NewClient(&redis.Options{
		Addr: fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort), Password: cfg.RedisPassword, DB: cfg.RedisDB,
	})
	h := handler.New(svc, delegate.New(cfg.PythonDelegateURL, cfg.InternalJobToken))
	consumer := queue.NewConsumer(rdb, h.Handle, cfg.VisibilityTimeout, cfg.MaxRetries, cfg.ConsumerPollInterval, cfg.ReclaimInterval, logger)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"status": "up", "role": "notify-worker"})
	})
	server := &http.Server{Addr: fmt.Sprintf(":%d", cfg.WorkerPort), Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = server.ListenAndServe() }()
	go func() { _ = consumer.Run(ctx) }()
	<-ctx.Done()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = server.Shutdown(shutdownCtx)
}
