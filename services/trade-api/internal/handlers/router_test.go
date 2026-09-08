package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestUnknownTradeRouteDoesNotProxy(t *testing.T) {
	tr := &TradeRouter{
		Native:   map[string]http.Handler{},
		Fallback: http.HandlerFunc(NotImplementedFallback),
	}
	req := httptest.NewRequest(http.MethodGet, "/trade/missing", nil)
	rec := httptest.NewRecorder()
	tr.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
	if rec.Body.String() != "route not implemented\n" {
		t.Fatalf("body %q", rec.Body.String())
	}
}
