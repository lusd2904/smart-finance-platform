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

	mwcfg "github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/delegate"
	mwinflux "github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/handler"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/store"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	cfg := mwcfg.Load()
	if cfg.WorkerPort == 9098 {
		cfg.WorkerPort = 9097
	}

	reader := mwinflux.NewReader(cfg)
	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		logger.Error("redis ping failed", "err", err)
		os.Exit(1)
	}

	svc, err := store.NewService(cfg, reader, rdb)
	if err != nil {
		logger.Error("mysql init failed", "err", err)
		os.Exit(1)
	}
	defer svc.Close()

	h := handler.New(svc, delegate.New(cfg.PythonDelegateURL, cfg.InternalJobToken))
	consumer := queue.NewConsumer(rdb, h.Handle, cfg.VisibilityTimeout, cfg.MaxRetries, cfg.ConsumerPollInterval, cfg.ReclaimInterval, logger)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		resp := map[string]interface{}{"status": "up", "role": "quant-worker", "queueDepth": consumer.QueueDepth(ctx)}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})

	server := &http.Server{Addr: fmt.Sprintf(":%d", cfg.WorkerPort), Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		logger.Info("quant worker listening", "port", cfg.WorkerPort)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("health server failed", "err", err)
			cancel()
		}
	}()
	go func() {
		if err := consumer.Run(ctx); err != nil && ctx.Err() == nil {
			logger.Error("consumer stopped", "err", err)
			cancel()
		}
	}()

	<-ctx.Done()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = server.Shutdown(shutdownCtx)
}
