package response

import (
	"encoding/json"
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

type envelope struct {
	Code    int         `json:"code"`
	Msg     string      `json:"msg"`
	Success bool        `json:"success"`
	Time    string      `json:"time"`
	Data    interface{} `json:"data,omitempty"`
}

type pageEnvelope struct {
	Code     int         `json:"code"`
	Msg      string      `json:"msg"`
	Success  bool        `json:"success"`
	Time     string      `json:"time"`
	Rows     interface{} `json:"rows"`
	PageNum  int         `json:"pageNum"`
	PageSize int         `json:"pageSize"`
	Total    int64       `json:"total"`
	HasNext  bool        `json:"hasNext"`
}

func Success(w http.ResponseWriter, data interface{}) {
	writeJSON(w, http.StatusOK, envelope{
		Code: 200, Msg: "操作成功", Success: true, Time: timeutil.NowBeijingRFC(), Data: data,
	})
}

func SuccessMsg(w http.ResponseWriter, msg string, data interface{}) {
	writeJSON(w, http.StatusOK, envelope{
		Code: 200, Msg: msg, Success: true, Time: timeutil.NowBeijingRFC(), Data: data,
	})
}

func Page(w http.ResponseWriter, rows interface{}, pageNum, pageSize int, total int64) {
	writeJSON(w, http.StatusOK, pageEnvelope{
		Code: 200, Msg: "操作成功", Success: true, Time: timeutil.NowBeijingRFC(),
		Rows: rows, PageNum: pageNum, PageSize: pageSize, Total: total,
		HasNext: int64(pageNum)*int64(pageSize) < total,
	})
}

func Unauthorized(w http.ResponseWriter, msg string) {
	writeJSON(w, http.StatusOK, envelope{Code: 401, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func Forbidden(w http.ResponseWriter, msg string) {
	writeJSON(w, http.StatusOK, envelope{Code: 403, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func Error(w http.ResponseWriter, msg string) {
	writeJSON(w, http.StatusOK, envelope{Code: 500, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func writeJSON(w http.ResponseWriter, status int, body interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
