package handlers

import (
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
)

// PythonProxy forwards unmigrated /trade/* routes to sentiment-trade (rollback path).
type PythonProxy struct {
	Target *url.URL
}

func NewPythonProxy(base string) (*PythonProxy, error) {
	if strings.TrimSpace(base) == "" {
		return nil, nil
	}
	u, err := url.Parse(strings.TrimRight(base, "/"))
	if err != nil {
		return nil, err
	}
	return &PythonProxy{Target: u}, nil
}

func (p *PythonProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if p == nil || p.Target == nil {
		http.Error(w, "route not implemented", http.StatusNotImplemented)
		return
	}
	proxy := httputil.NewSingleHostReverseProxy(p.Target)
	proxy.ErrorHandler = func(rw http.ResponseWriter, _ *http.Request, err error) {
		http.Error(rw, "sentiment-trade fallback unavailable: "+err.Error(), http.StatusBadGateway)
	}
	orig := r.URL.Path
	r.URL.Path = orig
	r.Host = p.Target.Host
	proxy.ServeHTTP(w, r)
}

// NotImplementedFallback is used when PythonTradeURL is empty and no native route matches.
func NotImplementedFallback(w http.ResponseWriter, r *http.Request) {
	http.Error(w, "route not implemented", http.StatusNotImplemented)
}

// TradeRouter dispatches native Go handlers or Python fallback.
type TradeRouter struct {
	Native   map[string]http.Handler
	Fallback http.Handler
}

func (tr *TradeRouter) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if h := tr.match(r.Method, r.URL.Path); h != nil {
		h.ServeHTTP(w, r)
		return
	}
	if tr.Fallback != nil {
		tr.Fallback.ServeHTTP(w, r)
		return
	}
	http.NotFound(w, r)
}

func (tr *TradeRouter) match(method, path string) http.Handler {
	if tr.Native == nil {
		return nil
	}
	key := method + " " + path
	if h, ok := tr.Native[key]; ok {
		return h
	}
	if method == "GET" && strings.HasPrefix(path, "/trade/order/") && !strings.HasSuffix(path, "/cancel") {
		return tr.Native["GET /trade/order/{id}"]
	}
	if method == "POST" && strings.HasPrefix(path, "/trade/order/") && strings.HasSuffix(path, "/cancel") {
		return tr.Native["POST /trade/order/{id}/cancel"]
	}
	if method == "GET" && strings.HasPrefix(path, "/trade/backtest/") {
		return tr.Native["GET /trade/backtest/{id}"]
	}
	if method == "DELETE" && strings.HasPrefix(path, "/trade/risk/rules/") {
		return tr.Native["DELETE /trade/risk/rules/{id}"]
	}
	if method == "PUT" && strings.HasPrefix(path, "/trade/risk/events/") && strings.HasSuffix(path, "/status") {
		return tr.Native["PUT /trade/risk/events/{id}/status"]
	}
	if method == "GET" && strings.HasPrefix(path, "/trade/ai/batches/") && strings.HasSuffix(path, "/items") {
		return tr.Native["GET /trade/ai/batches/{id}/items"]
	}
	if method == "PUT" && strings.HasPrefix(path, "/trade/strategy-profiles/") {
		return tr.Native["PUT /trade/strategy-profiles/{code}"]
	}
	return nil
}

func NoBody(w http.ResponseWriter) { w.WriteHeader(http.StatusNoContent) }

func Drain(r *http.Request) { io.Copy(io.Discard, r.Body) }
