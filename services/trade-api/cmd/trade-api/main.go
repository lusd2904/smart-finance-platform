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
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/autoscan"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/handlers"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/influx"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/internaljobs"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/middleware"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/platform"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/queue"
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

	tradeRepo := &repo.Repo{
		DB:            db,
		CredentialKey: cfg.CredentialKey,
		JWTSecret:     cfg.JWTSecret,
		AppEnv:        cfg.AppEnv,
	}
	broker := tradeexec.NewSDKBroker()
	defer tradeexec.CloseQuoteSessions()
	platformRepo := &platform.Repo{DB: db}

	srv := &handlers.Server{
		Trade: &service.Trade{
			Broker: broker,
			Repo:   tradeRepo,
			Redis:  cacheClient.Client(),
		},
		Quotes: &service.Quotes{
			Broker: tradeRepo,
			Influx: influx.New(cfg, db),
			Sdk:    broker,
		},
		Platform: &platform.Service{
			Repo:          platformRepo,
			Influx:        influx.New(cfg, db),
			Queue:         queue.NewEnqueuer(cacheClient.Client()),
			Broker:        broker,
			Redis:         cacheClient.Client(),
			CredentialKey: cfg.CredentialKey,
			JWTSecret:     cfg.JWTSecret,
			AppEnv:        cfg.AppEnv,
		},
		AutoScan: &autoscan.StrategyEvaluator{Jobs: internaljobs.New(cfg.InternalJobsURL, cfg.InternalJobToken)},
		AutoKeys: autoscan.Keys{
			CredentialKey: cfg.CredentialKey,
			JWTSecret:     cfg.JWTSecret,
			AppEnv:        cfg.AppEnv,
		},
	}

	wrap := func(perms []string, fn http.HandlerFunc) http.Handler {
		return mw.RequirePerms(perms...)(http.HandlerFunc(fn))
	}

	router := &handlers.TradeRouter{
		Fallback: http.HandlerFunc(handlers.NotImplementedFallback),
		Native: map[string]http.Handler{
			"GET /trade/account": wrap([]string{"trade:account:list"}, srv.Account),
			"GET /trade/positions": wrap([]string{"trade:position:list"}, srv.Positions),
			"GET /trade/orders": wrap([]string{"trade:order:list"}, srv.Orders),
			"GET /trade/order/{id}": wrap([]string{"trade:order:list"}, srv.OrderDetail),
			"POST /trade/order": wrap([]string{"trade:order:submit"}, srv.SubmitOrder),
			"POST /trade/order/{id}/cancel": wrap([]string{"trade:order:cancel"}, srv.CancelOrder),
			"GET /trade/quote/realtime": wrap([]string{"trade:position:list"}, srv.QuoteRealtime),
			"GET /trade/quote/depth": wrap([]string{"trade:account:list"}, srv.QuoteDepth),
			"GET /trade/quote/trades": wrap([]string{"trade:account:list"}, srv.QuoteTrades),
			"GET /trade/quote/kline": wrap([]string{"trade:account:list"}, srv.QuoteKline),
			"GET /trade/quote/snapshot": wrap([]string{"trade:account:list"}, srv.QuoteSnapshot),
			"GET /trade/halt": wrap([]string{"trade:order:submit", "trade:account:list", "trade:aitrade:list"}, srv.GetHalt),
			"PUT /trade/halt": wrap([]string{"trade:aitrade:run", "trade:risk:edit"}, srv.PutHalt),
			"GET /trade/auto/status": wrap([]string{"trade:aitrade:list", "quant:strategy:list", "quant:dailylist:list"}, srv.AutoStatus),
			"PUT /trade/auto/settings": wrap([]string{"trade:aitrade:run", "quant:strategy:list"}, srv.AutoSettings),
			"POST /trade/auto/run": wrap([]string{"trade:aitrade:run"}, srv.AutoRun),
			"GET /trade/notifications": wrap([]string{"trade:notice:list"}, srv.Notifications),
			"POST /trade/notifications/read": wrap([]string{"trade:notice:list"}, srv.NotificationsRead),
			"POST /trade/backtest/run": wrap([]string{"trade:backtest:run"}, srv.BacktestRun),
			"GET /trade/backtest/list": wrap([]string{"trade:backtest:list"}, srv.BacktestList),
			"GET /trade/backtest/{id}": wrap([]string{"trade:backtest:list"}, srv.BacktestDetail),
			"GET /trade/ai-trade-runs": wrap([]string{"trade:aitrade:list"}, srv.AiTradeRuns),
			"GET /trade/auto/decisions": wrap([]string{"trade:aitrade:list"}, srv.AutoDecisions),
			"GET /trade/coverage": wrap([]string{"market:kline:list"}, srv.Coverage),
			"GET /trade/strategy-profiles": wrap([]string{"quant:strategy:list"}, srv.StrategyProfiles),
			"PUT /trade/strategy-profiles/{code}": wrap([]string{"quant:strategy:list"}, srv.SaveStrategyProfile),
			"PUT /trade/strategy-bind": wrap([]string{"quant:strategy:list"}, srv.BindStrategy),
			"GET /trade/risk/tearsheet": wrap([]string{"trade:risk:list", "trade:position:list"}, srv.RiskTearsheet),
			"GET /trade/risk/rules": wrap([]string{"trade:risk:list"}, srv.RiskRules),
			"POST /trade/risk/rules": wrap([]string{"trade:risk:edit"}, srv.RiskRules),
			"DELETE /trade/risk/rules/{id}": wrap([]string{"trade:risk:edit"}, srv.DeleteRiskRule),
			"GET /trade/risk/events": wrap([]string{"trade:risk:list"}, srv.RiskEvents),
			"POST /trade/risk/evaluate": wrap([]string{"trade:risk:edit"}, srv.RiskEvaluate),
			"PUT /trade/risk/events/{id}/status": wrap([]string{"trade:risk:edit"}, srv.UpdateRiskEventStatus),
			"GET /trade/notices": wrap([]string{"trade:notice:list"}, srv.Notices),
			"POST /trade/notices/read": wrap([]string{"trade:notice:list"}, srv.NoticesRead),
			"POST /trade/ai/batch": wrap([]string{"market:ai:analyze"}, srv.SubmitAiBatch),
			"GET /trade/ai/batches": wrap([]string{"market:ai:analyze"}, srv.AiBatches),
			"GET /trade/ai/batches/{id}/items": wrap([]string{"market:ai:analyze"}, srv.AiBatchItems),
			"GET /trade/feishu/config": wrap([]string{"trade:feishu:query"}, srv.GetFeishuConfig),
			"PUT /trade/feishu/config": wrap([]string{"trade:feishu:edit"}, srv.PutFeishuConfig),
			"POST /trade/feishu/test": wrap([]string{"trade:feishu:test"}, srv.TestFeishu),
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
		log.Printf("trade-api listening on %s (native-only)", cfg.ListenAddr)
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
