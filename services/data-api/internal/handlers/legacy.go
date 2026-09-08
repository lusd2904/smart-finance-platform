package handlers

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/response"
)

type LegacyProxy struct {
	target *url.URL
	proxy  *httputil.ReverseProxy
}

func NewLegacyProxy() *LegacyProxy {
	raw := strings.TrimSpace(os.Getenv("LEGACY_DATA_URL"))
	if raw == "" {
		return &LegacyProxy{}
	}
	u, err := url.Parse(raw)
	if err != nil {
		return &LegacyProxy{}
	}
	return &LegacyProxy{target: u, proxy: httputil.NewSingleHostReverseProxy(u)}
}

func (p *LegacyProxy) Serve(w http.ResponseWriter, r *http.Request) bool {
	if p == nil || p.proxy == nil {
		response.Error(w, "该接口依赖 legacy Python sentiment-data，请启用 compose profile `--profile legacy-data` 并设置 LEGACY_DATA_URL")
		return false
	}
	r.URL.Scheme = p.target.Scheme
	r.URL.Host = p.target.Host
	r.Host = p.target.Host
	p.proxy.ServeHTTP(w, r)
	return true
}

func (s *Server) LegacyOr(w http.ResponseWriter, r *http.Request, fn http.HandlerFunc) {
	if s.Legacy != nil && s.Legacy.Serve(w, r) {
		return
	}
	fn(w, r)
}

func (s *Server) LegacyIndicators(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyAIStream(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacySymbolContent(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyFactorCompute(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyScanIndicators(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyScanPositions(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyLongbridgeConfigGet(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyLongbridgeConfigPut(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyLongbridgeTest(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyDailyListOpen(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}

func (s *Server) LegacyDailyListAuto(w http.ResponseWriter, r *http.Request) {
	s.LegacyOr(w, r, func(w http.ResponseWriter, r *http.Request) {})
}
