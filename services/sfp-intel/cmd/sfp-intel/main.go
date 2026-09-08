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

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/handlers"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/middleware"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/proxy"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/queue"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/store"
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

	st, err := store.New(cfg)
	if err != nil {
		log.Fatalf("mysql: %v", err)
	}

	aiProxy, err := proxy.NewPythonIntel(cfg.PythonIntelURL)
	if err != nil {
		log.Fatalf("python intel proxy: %v", err)
	}

	authn := auth.New(cfg, cacheClient.Client())
	mw := &middleware.Middleware{Auth: authn}
	enq := queue.NewEnqueuer(cacheClient.Client())
	srv := &handlers.Server{
		Cfg: cfg, Store: st, Queue: enq, AIProxy: aiProxy,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", srv.Health)
	mux.HandleFunc("/sentiment/ingest/x_monitor", srv.IngestXMonitor)

	mux.Handle("/sentiment/news/list", mw.RequirePerms("sentiment:news:list")(http.HandlerFunc(srv.NewsList)))
	mux.Handle("/sentiment/stats", mw.RequirePerms("sentiment:news:list")(http.HandlerFunc(srv.Stats)))
	mux.Handle("/sentiment/news/collect", mw.RequirePerms("sentiment:news:collect")(http.HandlerFunc(srv.CollectNews)))
	mux.Handle("/sentiment/analysis/list", mw.RequirePerms("sentiment:analysis:list")(http.HandlerFunc(srv.AnalysisList)))
	mux.Handle("/sentiment/analysis/trend", mw.RequirePerms("sentiment:analysis:list")(http.HandlerFunc(srv.AnalysisTrend)))
	mux.Handle("/sentiment/analysis/run", mw.RequirePerms("sentiment:analysis:run")(http.HandlerFunc(srv.RunAnalysis)))
	mux.Handle("/sentiment/config", routeConfig(mw, srv))
	mux.Handle("/sentiment/", routeSentimentSubpaths(mw, srv))
	mux.Handle("/ai/", http.HandlerFunc(srv.ProxyAI))

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("sfp-intel listening on %s (python fallback %s)", cfg.ListenAddr, cfg.PythonIntelURL)
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
	_ = st.Close()
	_ = cacheClient.Close()
}

func routeConfig(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			mw.RequirePerms("sentiment:config:query")(http.HandlerFunc(srv.GetConfig)).ServeHTTP(w, r)
		case http.MethodPut:
			mw.RequirePerms("sentiment:config:edit")(http.HandlerFunc(srv.SaveConfig)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeSentimentSubpaths(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if strings.HasPrefix(path, "/sentiment/news/") && r.Method == http.MethodDelete {
			mw.RequirePerms("sentiment:news:remove")(http.HandlerFunc(srv.DeleteNews)).ServeHTTP(w, r)
			return
		}
		if strings.HasPrefix(path, "/sentiment/analysis/") && r.Method == http.MethodGet {
			rest := strings.TrimPrefix(path, "/sentiment/analysis/")
			if rest != "list" && rest != "trend" && rest != "run" {
				mw.RequirePerms("sentiment:analysis:query")(http.HandlerFunc(srv.AnalysisDetail)).ServeHTTP(w, r)
				return
			}
		}
		http.NotFound(w, r)
	})
}
