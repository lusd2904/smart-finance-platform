package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/flow"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/handlers"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/jobqueue"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/store"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/auth"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/cache"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/config"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/influx"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/middleware"
	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

func main() {
	if os.Getenv("LISTEN_ADDR") == "" {
		_ = os.Setenv("LISTEN_ADDR", ":8081")
	}
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config: %v", err)
	}

	cacheClient := cache.New(cfg)
	if err := cacheClient.Ping(context.Background()); err != nil {
		log.Fatalf("redis: %v", err)
	}

	db, err := store.New(cfg)
	if err != nil {
		log.Fatalf("mysql: %v", err)
	}

	influxClient := influx.New(cfg)
	authn := auth.New(cfg, cacheClient.Client())
	mw := &middleware.Middleware{Auth: authn}
	srv := &handlers.Server{
		Auth:   authn,
		Cache:  cacheClient,
		Influx: influxClient,
		DB:     db,
		Queue:  jobqueue.New(cacheClient.Client()),
		Flow:   flow.New(cacheClient),
		Broker: tradeexec.NewSDKBroker(),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handlers.Health)

	// Jobs
	mux.Handle("/market/jobs/", mw.RequirePerms(
		"market:ai:analyze", "market:watchlist:list", "market:review:analyze", "market:picks:run", "market:heat:collect",
	)(http.HandlerFunc(srv.GetJobTicket)))

	// Market read
	mux.Handle("/market/instrument/list", mw.RequirePerms("market:instrument:list")(http.HandlerFunc(srv.InstrumentList)))
	mux.Handle("/market/instrument/universe", mw.RequirePerms("market:instrument:list")(http.HandlerFunc(srv.InstrumentUniverse)))
	mux.Handle("/market/finance/briefings", mw.RequirePerms("market:finance:list")(http.HandlerFunc(srv.FinanceBriefings)))
	mux.Handle("/market/review/latest", mw.RequirePerms("market:review:list")(http.HandlerFunc(srv.ReviewLatest)))
	mux.Handle("/market/review/history", mw.RequirePerms("market:review:list")(http.HandlerFunc(srv.ReviewHistory)))
	mux.Handle("/market/picks/mood", mw.RequirePerms("market:picks:list", "market:heat:list", "market:instrument:list")(http.HandlerFunc(srv.StockPickMood)))
	mux.Handle("/market/picks/dates", mw.RequirePerms("market:picks:list", "market:heat:list", "market:instrument:list")(http.HandlerFunc(srv.StockPickDates)))
	mux.Handle("/market/picks/latest", mw.RequirePerms("market:picks:list", "market:heat:list", "market:instrument:list")(http.HandlerFunc(srv.StockPickLatest)))
	mux.Handle("/market/watchlist/overview", mw.RequirePerms("market:watchlist:list")(http.HandlerFunc(srv.WatchlistOverview)))
	mux.Handle("/market/watchlist/list", mw.RequirePerms("market:watchlist:list")(http.HandlerFunc(srv.WatchlistList)))
	mux.Handle("/market/watchlist", mw.RequirePerms("market:watchlist:add")(http.HandlerFunc(routeWatchlistRoot(srv))))
	mux.Handle("/market/watchlist/analyze", mw.RequirePerms("market:watchlist:analyze")(http.HandlerFunc(srv.WatchlistAnalyze)))
	mux.Handle("/market/watchlist/", mw.RequirePerms("market:watchlist:list", "market:watchlist:remove")(http.HandlerFunc(routeWatchlistSub(srv))))
	mux.Handle("/market/symbols/", mw.RequirePerms("market:symbol:overview", "market:ai:analyze", "market:kline:list")(http.HandlerFunc(routeSymbols(srv))))
	mux.Handle("/market/flow/board", mw.RequirePerms("market:flow:list", "market:heat:list")(http.HandlerFunc(srv.FlowBoard)))
	mux.Handle("/market/tradingview/config", mw.RequirePerms("market:kline:list")(http.HandlerFunc(srv.TradingViewConfig)))
	mux.Handle("/market/tradingview/symbols", mw.RequirePerms("market:kline:list")(http.HandlerFunc(srv.TradingViewSymbols)))
	mux.Handle("/market/tradingview/history", mw.RequirePerms("market:kline:list")(http.HandlerFunc(srv.TradingViewHistory)))
	mux.Handle("/market/tradingview/time", mw.RequirePerms("market:kline:list")(http.HandlerFunc(srv.TradingViewTime)))

	// Market job POST
	mux.Handle("/market/sync", mw.RequirePerms("market:sync")(http.HandlerFunc(srv.MarketSync)))
	mux.Handle("/market/sync/mysql-to-influx", mw.RequirePerms("market:sync")(http.HandlerFunc(srv.MySQLToInflux)))
	mux.Handle("/market/heat/collect", mw.RequirePerms("market:heat:collect")(http.HandlerFunc(srv.HeatCollect)))
	mux.Handle("/market/picks/run", mw.RequirePerms("market:picks:run", "market:ai:analyze")(http.HandlerFunc(srv.StockPickRun)))
	mux.Handle("/market/picks/mood/refresh", mw.RequirePerms("market:picks:run", "market:ai:analyze")(http.HandlerFunc(srv.StockPickMoodRefresh)))
	mux.Handle("/market/ai/analyze", mw.RequirePerms("market:ai:analyze")(http.HandlerFunc(routeAIAnalyze(srv))))
	mux.Handle("/market/review/analyze", mw.RequirePerms("market:review:analyze")(http.HandlerFunc(srv.ReviewAnalyze)))

	// Native market/quant routes (Go; legacy-data profile is emergency rollback only)
	mux.Handle("/market/indicators", mw.RequirePerms("market:indicators:list")(http.HandlerFunc(srv.MarketIndicators)))
	mux.Handle("/market/ai/analyze/stream", mw.RequirePerms("market:ai:analyze")(http.HandlerFunc(srv.MarketAIAnalyzeStream)))

	// Quant read
	mux.Handle("/quant/factor/schema", mw.RequirePerms("quant:factor:list")(http.HandlerFunc(srv.FactorSchema)))
	mux.Handle("/quant/factor/snapshots/export", mw.RequirePerms("quant:factor:list")(http.HandlerFunc(srv.FactorSnapshotsExport)))
	mux.Handle("/quant/factor/snapshots", mw.RequirePerms("quant:factor:list")(http.HandlerFunc(srv.FactorSnapshots)))
	mux.Handle("/quant/factor/qc", mw.RequirePerms("quant:factor:list")(http.HandlerFunc(srv.FactorQC)))
	mux.Handle("/quant/watchlist/list", mw.RequirePerms("quant:watchlist:list")(http.HandlerFunc(srv.QuantWatchlistList)))
	mux.Handle("/quant/watchlist", mw.RequirePerms("quant:watchlist:add")(http.HandlerFunc(routeQuantWatchlistRoot(srv))))
	mux.Handle("/quant/watchlist/", mw.RequirePerms("quant:watchlist:remove")(http.HandlerFunc(routeQuantWatchlistDelete(srv))))
	mux.Handle("/quant/strategy/history", mw.RequirePerms("quant:strategy:history")(http.HandlerFunc(srv.StrategyHistory)))
	mux.Handle("/quant/scan-runs/", mw.RequirePerms("quant:scan:query")(http.HandlerFunc(srv.ScanRunDetail)))
	mux.Handle("/quant/scan-runs", mw.RequirePerms("quant:scan:list")(http.HandlerFunc(srv.ScanRuns)))
	mux.Handle("/quant/symbols/", mw.RequirePerms("quant:scan:query")(http.HandlerFunc(routeQuantSymbols(srv))))
	mux.Handle("/quant/daily-list", mw.RequirePerms("quant:dailylist:list")(http.HandlerFunc(srv.DailyList)))
	mux.Handle("/quant/readmodel/overview", mw.RequirePerms("quant:factor:list")(http.HandlerFunc(srv.ReadmodelOverview)))

	// Quant job POST
	mux.Handle("/quant/scan/daily", mw.RequirePerms("quant:strategy:run")(http.HandlerFunc(srv.QuantScanDaily)))
	mux.Handle("/quant/factor/qc/run", mw.RequirePerms("quant:factor:compute")(http.HandlerFunc(srv.QuantFactorQCRun)))
	mux.Handle("/quant/strategy/run", mw.RequirePerms("quant:strategy:run")(http.HandlerFunc(srv.QuantStrategyRun)))
	mux.Handle("/quant/daily-list/scan", mw.RequirePerms("quant:dailylist:scan")(http.HandlerFunc(srv.QuantDailyListScan)))

	// Native quant routes (Longbridge via openapi-go; factor via Go math)
	mux.Handle("/quant/factor/compute", mw.RequirePerms("quant:factor:compute")(http.HandlerFunc(srv.FactorCompute)))
	mux.Handle("/quant/scan/indicators", mw.RequirePerms("quant:factor:compute")(http.HandlerFunc(srv.ScanIndicators)))
	mux.Handle("/quant/scan/positions", mw.RequirePerms("quant:strategy:run")(http.HandlerFunc(srv.ScanPositions)))
	mux.Handle("/quant/longbridge/config", mw.RequirePerms("quant:longbridge:config")(http.HandlerFunc(routeLongbridgeConfig(srv))))
	mux.Handle("/quant/longbridge/test", mw.RequirePerms("quant:longbridge:test")(http.HandlerFunc(srv.LongbridgeTest)))
	mux.Handle("/quant/daily-list/open", mw.RequirePerms("quant:dailylist:open")(http.HandlerFunc(srv.DailyListOpen)))
	mux.Handle("/quant/daily-list/auto", mw.RequirePerms("quant:dailylist:auto")(http.HandlerFunc(srv.DailyListAuto)))

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("data-api listening on %s", cfg.ListenAddr)
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
	_ = db.Close()
	_ = cacheClient.Close()
}

func routeWatchlistRoot(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			srv.WatchlistAdd(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeWatchlistSub(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if r.Method == http.MethodDelete && strings.HasPrefix(path, "/market/watchlist/") {
			srv.WatchlistDelete(w, r)
			return
		}
		if r.Method == http.MethodGet && strings.HasSuffix(path, "/analysis") {
			srv.WatchlistAnalysis(w, r)
			return
		}
		if r.Method == http.MethodGet && strings.HasSuffix(path, "/backtest") {
			srv.WatchlistBacktest(w, r)
			return
		}
		if r.Method == http.MethodGet && strings.HasSuffix(path, "/correlation") {
			srv.WatchlistCorrelation(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeSymbols(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if r.Method == http.MethodGet && strings.HasSuffix(path, "/overview") {
			srv.SymbolOverview(w, r)
			return
		}
		if r.Method == http.MethodGet && strings.HasSuffix(path, "/ai/latest") {
			srv.SymbolAILatest(w, r)
			return
		}
		if r.Method == http.MethodPost && strings.HasSuffix(path, "/ai-analyze") {
			srv.SymbolAIAnalyze(w, r)
			return
		}
		if r.Method == http.MethodGet && strings.HasSuffix(path, "/content") {
			srv.SymbolContent(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeAIAnalyze(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			srv.MarketAIAnalyze(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeQuantWatchlistRoot(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			srv.QuantWatchlistAdd(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeQuantWatchlistDelete(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			srv.QuantWatchlistDelete(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeQuantSymbols(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/latest") {
			srv.SymbolLatestScan(w, r)
			return
		}
		http.NotFound(w, r)
	}
}

func routeLongbridgeConfig(srv *handlers.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			srv.LongbridgeConfigGet(w, r)
		case http.MethodPut:
			srv.LongbridgeConfigPut(w, r)
		default:
			http.NotFound(w, r)
		}
	}
}
