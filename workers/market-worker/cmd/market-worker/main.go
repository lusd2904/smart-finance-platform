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

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/handler"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/store"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	cfg := config.Load()

	writer, err := influx.NewWriter(cfg)
	if err != nil {
		logger.Error("influx init failed", "err", err)
		os.Exit(1)
	}
	defer writer.Close()

	reader := influx.NewReader(cfg)
	klineClient := kline.NewClient(cfg.SourceInterval)

	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		logger.Error("redis ping failed", "err", err)
		os.Exit(1)
	}

	syncStore, err := store.NewService(cfg, writer, reader, klineClient, rdb)
	if err != nil {
		logger.Error("mysql init failed", "err", err)
		os.Exit(1)
	}
	defer syncStore.Close()

	h := handler.New(syncStore, delegate.New(cfg.InternalJobsURL, cfg.InternalJobToken))
	consumer := queue.NewConsumer(
		rdb,
		h.Handle,
		cfg.VisibilityTimeout,
		cfg.MaxRetries,
		cfg.ConsumerPollInterval,
		cfg.ReclaimInterval,
		logger,
	)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		depth := consumer.QueueDepth(ctx)
		resp := map[string]interface{}{
			"status":     "up",
			"role":       "market-worker",
			"queueDepth": depth,
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, _ *http.Request) {
		depth := consumer.QueueDepth(ctx)
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		fmt.Fprintf(w, "# HELP sfp_market_queue_depth Redis market queue depth\n")
		fmt.Fprintf(w, "# TYPE sfp_market_queue_depth gauge\n")
		fmt.Fprintf(w, "sfp_market_queue_depth %d\n", depth)
	})

	server := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.WorkerPort),
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		logger.Info("health server listening", "port", cfg.WorkerPort)
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
	logger.Info("market worker stopped")
}
