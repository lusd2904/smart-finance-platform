package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/handlers"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/middleware"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/repo"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/service"
	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config: %v", err)
	}

	cacheClient := cache.New(cfg)
	if err := cacheClient.Ping(context.Background()); err != nil {
		log.Fatalf("redis: %v", err)
	}

	db, err := sql.Open("mysql", cfg.MySQLDSN())
	if err != nil {
		log.Fatalf("mysql open: %v", err)
	}
	defer db.Close()
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	if err := db.PingContext(context.Background()); err != nil {
		log.Fatalf("mysql ping: %v", err)
	}

	authn := auth.New(cfg, cacheClient.Client())
	mw := &middleware.Middleware{Auth: authn}
	srv := &handlers.Server{
		Trade: &service.Trade{
			Broker: tradeexec.NewSDKBroker(),
			Repo: &repo.Repo{
				DB:            db,
				CredentialKey: cfg.CredentialKey,
				JWTSecret:     cfg.JWTSecret,
				AppEnv:        cfg.AppEnv,
			},
			Redis: cacheClient.Client(),
		},
	}

	proxy, err := handlers.NewPythonProxy(cfg.PythonTradeURL)
	if err != nil {
		log.Fatalf("proxy: %v", err)
	}

	wrap := func(perms []string, fn http.HandlerFunc) http.Handler {
		return mw.RequirePerms(perms...)(http.HandlerFunc(fn))
	}

	router := &handlers.TradeRouter{
		Fallback: proxy,
		Native: map[string]http.Handler{
			"GET /trade/account": wrap([]string{"trade:account:list"}, srv.Account),
			"GET /trade/positions": wrap([]string{"trade:position:list"}, srv.Positions),
			"GET /trade/orders": wrap([]string{"trade:order:list"}, srv.Orders),
			"GET /trade/order/{id}": wrap([]string{"trade:order:list"}, srv.OrderDetail),
			"POST /trade/order": wrap([]string{"trade:order:submit"}, srv.SubmitOrder),
			"POST /trade/order/{id}/cancel": wrap([]string{"trade:order:cancel"}, srv.CancelOrder),
			"GET /trade/quote/realtime": wrap([]string{"trade:position:list"}, srv.QuoteRealtime),
			"GET /trade/halt": wrap([]string{"trade:order:submit", "trade:account:list", "trade:aitrade:list"}, srv.GetHalt),
			"PUT /trade/halt": wrap([]string{"trade:aitrade:run", "trade:risk:edit"}, srv.PutHalt),
			"GET /trade/auto/status": wrap([]string{"trade:aitrade:list", "quant:strategy:list", "quant:dailylist:list"}, srv.AutoStatus),
			"PUT /trade/auto/settings": wrap([]string{"trade:aitrade:run", "quant:strategy:list"}, srv.AutoSettings),
		},
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", srv.Health)
	mux.Handle("/trade/", router)
	mux.Handle("/trade", router)

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("trade-api listening on %s (python fallback %s)", cfg.ListenAddr, cfg.PythonTradeURL)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = server.Shutdown(ctx)
	_ = cacheClient.Close()
}
