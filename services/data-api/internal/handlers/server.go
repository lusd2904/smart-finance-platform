package handlers

import (
	"context"
	"encoding/json"
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/auth"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/cache"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/influx"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/timeutil"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/flow"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/jobqueue"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/store"
)

type Server struct {
	Auth    *auth.Authenticator
	Cache   *cache.Cache
	Influx  *influx.Client
	DB      *store.DB
	Queue   *jobqueue.Queue
	Flow    *flow.Service
	Legacy  *LegacyProxy
}

func Health(w http.ResponseWriter, _ *http.Request) {
	Success(w, map[string]string{"status": "ok", "service": "data-api"})
}

func Success(w http.ResponseWriter, data interface{}) {
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: "操作成功", Success: true, Time: timeutil.NowBeijingRFC(), Data: data})
}

func SuccessMsg(w http.ResponseWriter, msg string, data interface{}) {
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: msg, Success: true, Time: timeutil.NowBeijingRFC(), Data: data})
}

func SuccessPage(w http.ResponseWriter, page store.Page) {
	body := map[string]interface{}{
		"code": 200, "msg": "操作成功", "success": true, "time": timeutil.NowBeijingRFC(),
		"rows": page.Rows, "pageNum": page.PageNum, "pageSize": page.PageSize,
		"total": page.Total, "hasNext": page.HasNext,
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(body)
}

func SuccessPageExtra(w http.ResponseWriter, page store.Page, extra map[string]interface{}) {
	body := map[string]interface{}{
		"code": 200, "msg": "操作成功", "success": true, "time": timeutil.NowBeijingRFC(),
		"rows": page.Rows, "pageNum": page.PageNum, "pageSize": page.PageSize,
		"total": page.Total, "hasNext": page.HasNext,
	}
	for k, v := range extra {
		body[k] = v
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(body)
}

type envelope struct {
	Code    int         `json:"code"`
	Msg     string      `json:"msg"`
	Success bool        `json:"success"`
	Time    string      `json:"time"`
	Data    interface{} `json:"data,omitempty"`
}

func writeEnvelope(w http.ResponseWriter, status int, body envelope) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func requireUser(ctx context.Context) (int64, error) {
	user := auth.UserFrom(ctx)
	if user == nil || user.UserID <= 0 {
		return 0, errNoUser
	}
	return user.UserID, nil
}
