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

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/analysis"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/dashboard"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/handlers"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/internaljobs"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/jobqueue"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/middleware"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/opensync"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/scheduler"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/transportcrypto"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/ws"
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

	db, err := store.Open(cfg)
	if err != nil {
		log.Fatalf("mysql: %v", err)
	}

	authSvc := auth.New(cfg, cacheClient.Client(), db)
	mw := &middleware.Middleware{Auth: authSvc}
	sched := scheduler.New(cacheClient.Client())
	commander := scheduler.NewCommander(cacheClient.Client())
	enqueuer := jobqueue.New(cacheClient.Client(), nil)

	srv := &handlers.Server{
		Auth:      authSvc,
		DB:        db,
		Config:    cfg,
		Redis:     cacheClient.Client(),
		Scheduler: sched,
		Commander: commander,
		Dashboard: dashboard.New(db, cacheClient.Client(), sched),
		Analysis:  analysis.New(db, sched, commander, cfg.AppRole),
	}

	cryptoProvider, err := transportcrypto.NewProvider(
		cfg.TransportCryptoEnabled,
		cfg.TransportCryptoMode,
		cfg.TransportCryptoAlgorithm,
		cfg.TransportCryptoKID,
		cfg.TransportCryptoPrivateKey,
		cfg.TransportCryptoPublicKey,
		cfg.TransportCryptoLegacyPairs,
	)
	if err != nil {
		log.Fatalf("transport crypto: %v", err)
	}
	srv.Crypto = cryptoProvider
	cryptoMW := transportcrypto.NewMiddleware(
		cryptoProvider,
		transportcrypto.SplitPaths(cfg.TransportCryptoEnabledPaths),
		transportcrypto.SplitPaths(cfg.TransportCryptoRequiredPaths),
	)

	platform := &handlers.PlatformServer{
		Server: srv,
		Sync:   opensync.New(cfg, db, cacheClient.Client()),
		Jobs:   internaljobs.New(cfg.InternalJobToken, cfg.IntelJobsURL, cfg.QuantJobsURL, enqueuer),
	}
	jobsWS := &ws.JobsGateway{Auth: authSvc, Scheduler: sched}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", srv.Health)
	mux.HandleFunc("/captchaImage", srv.CaptchaImage)
	mux.HandleFunc("/login", methodPOST(srv.Login))
	mux.HandleFunc("/register", methodPOST(srv.Register))
	mux.Handle("/getInfo", mw.RequireAuth(http.HandlerFunc(srv.GetInfo)))
	mux.Handle("/getRouters", mw.RequireAuth(http.HandlerFunc(srv.GetRouters)))
	mux.HandleFunc("/logout", methodPOST(srv.Logout))

	mux.Handle("/ws/jobs", jobsWS)
	mux.HandleFunc("/open/sync/token", cryptoMW.Wrap("/open/sync/token", methodPOST(platform.OpenSyncToken)))
	mux.HandleFunc("/open/sync/pull", cryptoMW.Wrap("/open/sync/pull", methodPOST(platform.OpenSyncPull)))
	mux.HandleFunc("/internal/jobs/run", platform.InternalJobsRun)

	mux.HandleFunc("/transport/crypto/frontend-config", srv.TransportFrontendConfig)
	mux.HandleFunc("/transport/crypto/public-key", srv.TransportPublicKey)

	mux.Handle("/dashboard/summary", mw.RequirePerms("system:user:query")(http.HandlerFunc(srv.DashboardSummary)))

	mux.Handle("/analysis/scheduler/overview", mw.RequirePerms("analysis:job:list")(http.HandlerFunc(srv.AnalysisSchedulerOverview)))
	mux.Handle("/analysis/scheduler/jobs/", analysisJobRoutes(mw, srv))

	mux.Handle("/system/dict/data/type/", mw.RequireAuth(http.HandlerFunc(srv.DictDataByType)))
	mux.Handle("/system/config/configKey/", mw.RequireAuth(http.HandlerFunc(srv.ConfigByKey)))

	mux.Handle("/common/upload", mw.RequireAuth(http.HandlerFunc(methodPOST(srv.CommonUpload))))
	mux.Handle("/common/guide/", mw.RequireAuth(http.HandlerFunc(srv.CommonGuide)))
	mux.Handle("/common/download", mw.RequireAuth(http.HandlerFunc(srv.CommonDownload)))
	mux.Handle("/common/download/resource", mw.RequireAuth(http.HandlerFunc(srv.CommonDownloadResource)))

	registerSystemRoutes(mux, mw, srv)

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("sfp-backend listening on %s", cfg.ListenAddr)
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
	_ = db.Close()
	_ = cacheClient.Close()
}

func analysisJobRoutes(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		switch {
		case strings.HasSuffix(path, "/status") && r.Method == http.MethodPut:
			mw.RequirePerms("analysis:job:edit")(http.HandlerFunc(srv.AnalysisJobStatus)).ServeHTTP(w, r)
		case strings.HasSuffix(path, "/run") && r.Method == http.MethodPost:
			mw.RequirePerms("analysis:job:run")(http.HandlerFunc(srv.AnalysisJobRun)).ServeHTTP(w, r)
		case strings.HasSuffix(path, "/logs") && r.Method == http.MethodGet:
			mw.RequirePerms("analysis:job:query")(http.HandlerFunc(srv.AnalysisJobLogs)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func registerSystemRoutes(mux *http.ServeMux, mw *middleware.Middleware, srv *handlers.Server) {
	mux.Handle("/system/user/list", mw.RequirePerms("system:user:list")(http.HandlerFunc(srv.UserList)))
	mux.Handle("/system/user/deptTree", mw.RequirePerms("system:user:list")(http.HandlerFunc(srv.UserDeptTree)))
	mux.Handle("/system/user/resetPwd", mw.RequirePerms("system:user:resetPwd")(http.HandlerFunc(methodPUTHandler(srv.UserResetPwd))))
	mux.Handle("/system/user/changeStatus", mw.RequirePerms("system:user:edit")(http.HandlerFunc(methodPUTHandler(srv.UserChangeStatus))))
	mux.Handle("/system/user/authRole", mw.RequirePerms("system:user:edit")(http.HandlerFunc(methodPUTHandler(srv.UserAuthRolePut))))
	mux.Handle("/system/user", routeCRUD(mw, srv,
		[]string{"system:user:list"},
		[]string{"system:user:add"},
		[]string{"system:user:edit"},
		[]string{"system:user:remove"},
		srv.UserGet, srv.UserAdd, srv.UserEdit, srv.UserDelete,
	))
	mux.Handle("/system/user/", userSubRoutes(mw, srv))

	mux.Handle("/system/menu/list", mw.RequirePerms("system:menu:list")(http.HandlerFunc(srv.MenuList)))
	mux.Handle("/system/menu/treeselect", mw.RequireAuth(http.HandlerFunc(srv.MenuTreeSelect)))
	mux.Handle("/system/menu/roleMenuTreeselect/", mw.RequireAuth(http.HandlerFunc(srv.MenuRoleTreeSelect)))
	mux.Handle("/system/menu", routeCRUD(mw, srv,
		nil, []string{"system:menu:add"}, []string{"system:menu:edit"}, []string{"system:menu:remove"},
		srv.MenuGet, srv.MenuAdd, srv.MenuEdit, srv.MenuDelete,
	))
	mux.Handle("/system/menu/", routeByID(mw, srv,
		[]string{"system:menu:query"}, []string{"system:menu:remove"},
		srv.MenuGet, srv.MenuDelete,
	))

	mux.Handle("/system/role/list", mw.RequirePerms("system:role:list")(http.HandlerFunc(srv.RoleList)))
	mux.Handle("/system/role/changeStatus", mw.RequirePerms("system:role:edit")(http.HandlerFunc(methodPUTHandler(srv.RoleChangeStatus))))
	mux.Handle("/system/role/dataScope", mw.RequirePerms("system:role:edit")(http.HandlerFunc(methodPUTHandler(srv.RoleDataScope))))
	mux.Handle("/system/role/deptTree/", mw.RequirePerms("system:role:query")(http.HandlerFunc(srv.RoleDeptTree)))
	mux.Handle("/system/role/authUser/allocatedList", mw.RequirePerms("system:role:list")(http.HandlerFunc(srv.RoleAuthUserAllocated)))
	mux.Handle("/system/role/authUser/unallocatedList", mw.RequirePerms("system:role:list")(http.HandlerFunc(srv.RoleAuthUserUnallocated)))
	mux.Handle("/system/role/authUser/cancel", mw.RequirePerms("system:role:edit")(http.HandlerFunc(methodPUTHandler(srv.RoleAuthUserCancel))))
	mux.Handle("/system/role/authUser/cancelAll", mw.RequirePerms("system:role:edit")(http.HandlerFunc(methodPUTHandler(srv.RoleAuthUserCancelAll))))
	mux.Handle("/system/role/authUser/selectAll", mw.RequirePerms("system:role:edit")(http.HandlerFunc(methodPUTHandler(srv.RoleAuthUserSelectAll))))
	mux.Handle("/system/role", routeCRUD(mw, srv,
		nil, []string{"system:role:add"}, []string{"system:role:edit"}, []string{"system:role:remove"},
		srv.RoleGet, srv.RoleAdd, srv.RoleEdit, srv.RoleDelete,
	))
	mux.Handle("/system/role/", routeByID(mw, srv,
		[]string{"system:role:query"}, []string{"system:role:remove"},
		srv.RoleGet, srv.RoleDelete,
	))
}

func userSubRoutes(mw *middleware.Middleware, srv *handlers.Server) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if strings.HasPrefix(path, "/system/user/authRole/") {
			mw.RequirePerms("system:user:query")(http.HandlerFunc(srv.UserAuthRoleGet)).ServeHTTP(w, r)
			return
		}
		routeByID(mw, srv,
			[]string{"system:user:query"}, []string{"system:user:remove"},
			srv.UserGet, srv.UserDelete,
		).ServeHTTP(w, r)
	})
}

func routeCRUD(mw *middleware.Middleware, srv *handlers.Server, getPerms, addPerms, editPerms, delPerms []string,
	getFn, addFn, editFn, delFn http.HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			if len(getPerms) > 0 {
				mw.RequirePerms(getPerms...)(http.HandlerFunc(getFn)).ServeHTTP(w, r)
			} else {
				mw.RequireAuth(http.HandlerFunc(getFn)).ServeHTTP(w, r)
			}
		case http.MethodPost:
			mw.RequirePerms(addPerms...)(http.HandlerFunc(addFn)).ServeHTTP(w, r)
		case http.MethodPut:
			mw.RequirePerms(editPerms...)(http.HandlerFunc(editFn)).ServeHTTP(w, r)
		case http.MethodDelete:
			mw.RequirePerms(delPerms...)(http.HandlerFunc(delFn)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func routeByID(mw *middleware.Middleware, srv *handlers.Server, getPerms, delPerms []string, getFn, delFn http.HandlerFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			mw.RequirePerms(getPerms...)(http.HandlerFunc(getFn)).ServeHTTP(w, r)
		case http.MethodDelete:
			mw.RequirePerms(delPerms...)(http.HandlerFunc(delFn)).ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}

func methodPOST(fn http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.NotFound(w, r)
			return
		}
		fn(w, r)
	}
}

func methodPUTHandler(fn http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPut {
			http.NotFound(w, r)
			return
		}
		fn(w, r)
	}
}
