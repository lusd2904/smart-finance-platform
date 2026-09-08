package response

import (
	"encoding/json"
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/timeutil"
)

type envelope struct {
	Code    int         `json:"code"`
	Msg     string      `json:"msg"`
	Success bool        `json:"success"`
	Time    string      `json:"time"`
	Data    interface{} `json:"data,omitempty"`
}

func Success(w http.ResponseWriter, data interface{}) {
	write(w, http.StatusOK, envelope{
		Code:    200,
		Msg:     "操作成功",
		Success: true,
		Time:    timeutil.NowBeijingRFC(),
		Data:    data,
	})
}

func Unauthorized(w http.ResponseWriter, msg string) {
	write(w, http.StatusOK, envelope{
		Code:    401,
		Msg:     msg,
		Success: false,
		Time:    timeutil.NowBeijingRFC(),
	})
}

func Forbidden(w http.ResponseWriter, msg string) {
	write(w, http.StatusOK, envelope{
		Code:    403,
		Msg:     msg,
		Success: false,
		Time:    timeutil.NowBeijingRFC(),
	})
}

func Error(w http.ResponseWriter, msg string) {
	write(w, http.StatusOK, envelope{
		Code:    500,
		Msg:     msg,
		Success: false,
		Time:    timeutil.NowBeijingRFC(),
	})
}

func write(w http.ResponseWriter, status int, body envelope) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
