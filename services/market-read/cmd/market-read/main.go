package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/handlers"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/influx"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/middleware"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/quotes"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/store"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/tencent"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/ws"
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

	heatStore, err := store.NewHeatStore(cfg)
	if err != nil {
		log.Fatalf("mysql: %v", err)
	}

	influxClient := influx.New(cfg)
	authn := auth.New(cfg, cacheClient.Client())
	mw := &middleware.Middleware{Auth: authn}
	quoteSvc := &quotes.Service{
		Cache:   cacheClient,
		Fetcher: tencent.NewHTTPFetcher(),
	}
	srv := &handlers.Server{
		Auth:   authn,
		Influx: influxClient,
		Heat:   heatStore,
		Cache:  cacheClient,
		Quotes: quoteSvc,
	}
	wsGateway := &ws.Gateway{Auth: authn, Quotes: quoteSvc}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", srv.Health)

	mux.Handle("/market/kline", mw.RequirePerms("market:kline:list")(http.HandlerFunc(srv.Kline)))
	mux.Handle("/market/board/quotes", mw.RequirePerms("market:kline:list")(http.HandlerFunc(srv.BoardQuotes)))
	mux.Handle("/market/heat/daily", mw.RequirePerms("market:heat:list")(http.HandlerFunc(srv.HeatDaily)))
	mux.Handle("/market/heat/trend", mw.RequirePerms("market:heat:list")(http.HandlerFunc(srv.HeatTrend)))
	mux.Handle("/market/heat/dates", mw.RequirePerms("market:heat:list")(http.HandlerFunc(srv.HeatDates)))
	mux.Handle("/market/heat/config", mw.RequirePerms("market:heat:list")(http.HandlerFunc(srv.HeatConfig)))
	mux.Handle("/market/index/quotes", mw.RequirePerms(
		"sentiment:news:list", "sentiment:analysis:list", "market:heat:list",
	)(http.HandlerFunc(srv.IndexQuotes)))
	mux.Handle("/market/quotes/live", mw.RequirePerms(
		"sentiment:news:list", "sentiment:analysis:list", "market:heat:list", "market:kline:list", "market:watchlist:list",
	)(http.HandlerFunc(srv.LiveQuotes)))
	mux.Handle("/market/symbols/", mw.RequirePerms("market:kline:list")(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if stringsHasSuffix(r.URL.Path, "/history") {
			srv.SymbolHistory(w, r)
			return
		}
		http.NotFound(w, r)
	})))
	// Same FE contract as Python WS /ws/market/quotes (JWT+session; no extra perm).
	mux.HandleFunc("/ws/market/quotes", wsGateway.ServeMarketQuotes)

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("market-read listening on %s", cfg.ListenAddr)
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
	influxClient.Close()
	_ = heatStore.Close()
	_ = cacheClient.Close()
}

func stringsHasSuffix(s, suffix string) bool {
	return len(s) >= len(suffix) && s[len(s)-len(suffix):] == suffix
}
