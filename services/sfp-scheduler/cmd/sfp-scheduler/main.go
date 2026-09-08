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

	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/scheduler"
	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/store"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	cfg := config.Load()

	loc, err := time.LoadLocation(cfg.Timezone)
	if err != nil {
		logger.Error("invalid timezone", "tz", cfg.Timezone, "err", err)
		os.Exit(1)
	}

	st, err := store.Open(store.DSN(cfg.MySQLHost, cfg.MySQLPort, cfg.MySQLUser, cfg.MySQLPassword, cfg.MySQLDatabase))
	if err != nil {
		logger.Error("mysql init failed", "err", err)
		os.Exit(1)
	}
	defer st.Close()

	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		logger.Error("redis ping failed", "err", err)
		os.Exit(1)
	}

	host, _ := os.Hostname()
	workerID := fmt.Sprintf("sfp-scheduler-%s-%d", host, os.Getpid())
	engine := scheduler.New(cfg, st, rdb, loc, logger, workerID)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		depth := engine.QueueDepth(ctx)
		resp := map[string]any{
			"status":           "up",
			"role":             "scheduler",
			"jobGroup":         "none",
			"leader":           engine.IsLeader(),
			"schedulerRunning": engine.Running(),
			"queueDepth":       depth,
			"engine":           "sfp-scheduler",
			"timezone":         loc.String(),
			"jobsLoaded":       engine.JobCount(),
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	})
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, _ *http.Request) {
		depth := engine.QueueDepth(ctx)
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		fmt.Fprintf(w, "# HELP sfp_scheduler_queue_depth Redis job queue depth (market+quant+llm)\n")
		fmt.Fprintf(w, "# TYPE sfp_scheduler_queue_depth gauge\n")
		fmt.Fprintf(w, "sfp_scheduler_queue_depth %d\n", depth)
		fmt.Fprintf(w, "# HELP sfp_scheduler_jobs_loaded Enabled jobs currently scheduled\n")
		fmt.Fprintf(w, "# TYPE sfp_scheduler_jobs_loaded gauge\n")
		fmt.Fprintf(w, "sfp_scheduler_jobs_loaded %d\n", engine.JobCount())
		leader := 0
		if engine.IsLeader() {
			leader = 1
		}
		fmt.Fprintf(w, "# HELP sfp_scheduler_leader 1 if this instance holds app:scheduler:lock\n")
		fmt.Fprintf(w, "# TYPE sfp_scheduler_leader gauge\n")
		fmt.Fprintf(w, "sfp_scheduler_leader %d\n", leader)
	})

	server := &http.Server{
		Addr:              fmt.Sprintf(":%d", cfg.ListenPort),
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		logger.Info("health server listening", "port", cfg.ListenPort, "tz", loc.String(), "redisDB", cfg.RedisDB)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("health server failed", "err", err)
			cancel()
		}
	}()

	go func() {
		if err := engine.Run(ctx); err != nil && ctx.Err() == nil {
			logger.Error("scheduler stopped", "err", err)
			cancel()
		}
	}()

	<-ctx.Done()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = server.Shutdown(shutdownCtx)
	logger.Info("sfp-scheduler stopped")
}
