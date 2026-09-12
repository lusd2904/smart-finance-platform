package handlers

import (
	"encoding/json"
	"errors"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

func TestWriteTradeErr401004IsNotSessionJWT(t *testing.T) {
	rec := httptest.NewRecorder()
	writeTradeErr(rec, tradeexec.ClassifyBrokerError(errors.New("401004 access token invalid")))
	var body struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Code != 401004 {
		t.Fatalf("code=%d body=%s", body.Code, rec.Body.String())
	}
	if strings.Contains(body.Msg, "请重新登录") || strings.Contains(body.Msg, "用户token已失效") {
		t.Fatalf("must not look like JWT expiry: %s", body.Msg)
	}
	if !strings.Contains(body.Msg, "OpenAPI") {
		t.Fatalf("msg=%s", body.Msg)
	}
}

func TestWriteTradeErrGenericStays500(t *testing.T) {
	rec := httptest.NewRecorder()
	writeTradeErr(rec, errors.New("network timeout"))
	var body struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Code != 500 || body.Msg != "network timeout" {
		t.Fatalf("body=%+v", body)
	}
}
