package response

import (
	"encoding/json"
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/timeutil"
)

type envelope struct {
	Code    int         `json:"code"`
	Msg     string      `json:"msg"`
	Success bool        `json:"success"`
	Time    string      `json:"time"`
	Data    interface{} `json:"data,omitempty"`
	Rows    interface{} `json:"rows,omitempty"`
}

func Success(w http.ResponseWriter, data interface{}) {
	write(w, envelope{
		Code: 200, Msg: "操作成功", Success: true,
		Time: timeutil.NowBeijingRFC(), Data: data,
	})
}

func SuccessMsg(w http.ResponseWriter, msg string) {
	write(w, envelope{
		Code: 200, Msg: msg, Success: true, Time: timeutil.NowBeijingRFC(),
	})
}

func SuccessFlat(w http.ResponseWriter, msg string, extra map[string]interface{}) {
	body := envelope{Code: 200, Msg: msg, Success: true, Time: timeutil.NowBeijingRFC()}
	raw, _ := json.Marshal(body)
	var m map[string]interface{}
	_ = json.Unmarshal(raw, &m)
	for k, v := range extra {
		m[k] = v
	}
	writeMap(w, m)
}

func SuccessModel(w http.ResponseWriter, msg string, model map[string]interface{}) {
	body := envelope{Code: 200, Msg: msg, Success: true, Time: timeutil.NowBeijingRFC()}
	raw, _ := json.Marshal(body)
	var m map[string]interface{}
	_ = json.Unmarshal(raw, &m)
	for k, v := range model {
		m[k] = v
	}
	writeMap(w, m)
}

func Page(w http.ResponseWriter, rows interface{}, pageNum, pageSize, total int, hasNext bool) {
	writeMap(w, map[string]interface{}{
		"code": 200, "msg": "操作成功", "success": true, "time": timeutil.NowBeijingRFC(),
		"rows": rows, "pageNum": pageNum, "pageSize": pageSize, "total": total, "hasNext": hasNext,
	})
}

func Unauthorized(w http.ResponseWriter, msg string) {
	write(w, envelope{Code: 401, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func Forbidden(w http.ResponseWriter, msg string) {
	write(w, envelope{Code: 403, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func Error(w http.ResponseWriter, msg string) {
	write(w, envelope{Code: 500, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func Warn(w http.ResponseWriter, msg string) {
	write(w, envelope{Code: 601, Msg: msg, Success: false, Time: timeutil.NowBeijingRFC()})
}

func write(w http.ResponseWriter, body envelope) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(body)
}

func writeMap(w http.ResponseWriter, body map[string]interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(body)
}
