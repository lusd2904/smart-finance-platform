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
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/jobs"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/llm"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/middleware"
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
	if err := st.EnsureChatSchema(context.Background()); err != nil {
		log.Fatalf("chat schema: %v", err)
	}

	authn := auth.New(cfg, cacheClient.Client())
	mw := &middleware.Middleware{Auth: authn}
	enq := queue.NewEnqueuer(cacheClient.Client())
	srv := &handlers.Server{
		Cfg: cfg, Store: st, Queue: enq,
		Redis: cacheClient.Client(), Runs: llm.NewRunRegistry(),
	}
	internalJobs := &handlers.InternalJobs{Runner: &jobs.Runner{Store: st}, Token: cfg.InternalJobToken}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", srv.Health)
	mux.HandleFunc("/internal/jobs/run", internalJobs.Run)
	mux.HandleFunc("/sentiment/ingest/x_monitor", srv.IngestXMonitor)

	mux.Handle("/sentiment/news/list", mw.RequirePerms("sentiment:news:list")(http.HandlerFunc(srv.NewsList)))
	mux.Handle("/sentiment/stats", mw.RequirePerms("sentiment:news:list")(http.HandlerFunc(srv.Stats)))
	mux.Handle("/sentiment/news/collect", mw.RequirePerms("sentiment:news:collect")(http.HandlerFunc(srv.CollectNews)))
	mux.Handle("/sentiment/analysis/list", mw.RequirePerms("sentiment:analysis:list")(http.HandlerFunc(srv.AnalysisList)))
	mux.Handle("/sentiment/analysis/trend", mw.RequirePerms("sentiment:analysis:list")(http.HandlerFunc(srv.AnalysisTrend)))
	mux.Handle("/sentiment/analysis/run", mw.RequirePerms("sentiment:analysis:run")(http.HandlerFunc(srv.RunAnalysis)))
	mux.Handle("/sentiment/config", routeConfig(mw, srv))
	mux.Handle("/sentiment/", routeSentimentSubpaths(mw, srv))

	registerAIRoutes(mux, mw, srv)
	registerOpenRoutes(mux, srv)

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("sfp-intel listening on %s", cfg.ListenAddr)
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

func registerAIRoutes(mux *http.ServeMux, mw *middleware.Middleware, srv *handlers.Server) {
	mux.Handle("/ai/chat/send", mw.RequireAuth(http.HandlerFunc(srv.ChatSend)))
	mux.Handle("/ai/chat/config", routeChatConfig(mw, srv))
	mux.Handle("/ai/chat/cancel", mw.RequireAuth(http.HandlerFunc(srv.ChatCancel)))
	mux.Handle("/ai/chat/consultant", mw.RequireAuth(http.HandlerFunc(srv.ChatConsultant)))
	mux.Handle("/ai/chat/oneshot", mw.RequireAuth(http.HandlerFunc(srv.ChatOneshot)))
	mux.Handle("/ai/chat/session/list", mw.RequireAuth(http.HandlerFunc(srv.ChatSessionList)))
	mux.Handle("/ai/chat/session/", routeChatSession(mw, srv))

	mux.Handle("/ai/model/list", mw.RequirePerms("ai:model:list")(http.HandlerFunc(srv.AiModelList)))
	mux.Handle("/ai/model/all", mw.RequireAuth(http.HandlerFunc(srv.AiModelAll)))
	mux.Handle("/ai/model", routeAiModelCRUD(mw, srv))
	mux.Handle("/ai/model/", routeAiModelByID(mw, srv))

	mux.Handle("/ai/req/bots", routeReqBots(mw, srv))
	mux.Handle("/ai/req/room", mw.RequirePerms("ai:req:chat")(http.HandlerFunc(srv.ReqRoom)))
	mux.Handle("/ai/req/messages", routeReqMessages(mw, srv))
	mux.Handle("/ai/req/summarize", mw.RequirePerms("ai:req:chat")(http.HandlerFunc(srv.ReqSummarize)))
	mux.Handle("/ai/req/jobs/", mw.RequirePerms("ai:req:chat")(http.HandlerFunc(srv.ReqJobStatus)))
	mux.Handle("/ai/req/items/export", mw.RequirePerms("ai:req:list")(http.HandlerFunc(srv.ReqItemsExport)))
	mux.Handle("/ai/req/items/", routeReqItemStatus(mw, srv))
	mux.Handle("/ai/req/items", mw.RequirePerms("ai:req:list")(http.HandlerFunc(srv.ReqItemsGet)))
}

func registerOpenRoutes(mux *http.ServeMux, srv *handlers.Server) {
	mux.HandleFunc("/open/token", srv.OpenToken)
	mux.HandleFunc("/open/requirements", srv.OpenRequirements)
}

func routeChatConfig(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			mw.RequireAuth(http.HandlerFunc(srv.ChatConfigGet)).ServeHTTP(w, r)
		case http.MethodPut:
			mw.RequireAuth(http.HandlerFunc(srv.ChatConfigSave)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeChatSession(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			mw.RequireAuth(http.HandlerFunc(srv.ChatSessionDetail)).ServeHTTP(w, r)
		case http.MethodDelete:
			mw.RequireAuth(http.HandlerFunc(srv.ChatSessionDelete)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeAiModelCRUD(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodPost:
			mw.RequirePerms("ai:model:add")(http.HandlerFunc(srv.AiModelAdd)).ServeHTTP(w, r)
		case http.MethodPut:
			mw.RequirePerms("ai:model:edit")(http.HandlerFunc(srv.AiModelEdit)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeAiModelByID(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if path == "/ai/model/list" || path == "/ai/model/all" {
			http.NotFound(w, r)
			return
		}
		switch r.Method {
		case http.MethodGet:
			mw.RequirePerms("ai:model:query")(http.HandlerFunc(srv.AiModelDetail)).ServeHTTP(w, r)
		case http.MethodDelete:
			mw.RequirePerms("ai:model:remove")(http.HandlerFunc(srv.AiModelDelete)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeReqBots(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			mw.RequirePerms("ai:req:bot")(http.HandlerFunc(srv.ReqBotsGet)).ServeHTTP(w, r)
		case http.MethodPut:
			mw.RequirePerms("ai:req:bot:edit")(http.HandlerFunc(srv.ReqBotsPut)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeReqMessages(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			mw.RequirePerms("ai:req:chat")(http.HandlerFunc(srv.ReqMessagesGet)).ServeHTTP(w, r)
		case http.MethodPost:
			mw.RequirePerms("ai:req:chat")(http.HandlerFunc(srv.ReqMessagesPost)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeReqItemStatus(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/status") && r.Method == http.MethodPut {
			mw.RequirePerms("ai:req:edit")(http.HandlerFunc(srv.ReqItemStatusPut)).ServeHTTP(w, r)
			return
		}
		http.NotFound(w, r)
	})
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
