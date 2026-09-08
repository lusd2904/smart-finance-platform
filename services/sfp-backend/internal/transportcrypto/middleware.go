package transportcrypto

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

const (
	headerEncryptRequest  = "x-transport-encrypt"
	headerEncryptResponse = "x-body-encrypted"
	headerEncryptAlg      = "x-encrypt-alg"
	headerEncryptKID      = "x-key-id"
)

type Middleware struct {
	Provider       *Provider
	EnabledPaths   map[string]bool
	RequiredPaths  map[string]bool
}

func NewMiddleware(p *Provider, enabledPaths, requiredPaths []string) *Middleware {
	m := &Middleware{Provider: p, EnabledPaths: map[string]bool{}, RequiredPaths: map[string]bool{}}
	for _, path := range enabledPaths {
		m.EnabledPaths[path] = true
	}
	for _, path := range requiredPaths {
		m.RequiredPaths[path] = true
	}
	return m
}

func (m *Middleware) Wrap(path string, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if m.Provider == nil || !m.Provider.Enabled() || !m.EnabledPaths[path] {
			next(w, r)
			return
		}
		encrypted := r.Header.Get(headerEncryptRequest) == "1"
		required := m.Provider.Mode() == "required" || m.RequiredPaths[path]
		if required && !encrypted {
			response.Error(w, "当前接口要求使用加密传输")
			return
		}
		if !encrypted {
			next(w, r)
			return
		}
		body, err := io.ReadAll(r.Body)
		if err != nil {
			response.Error(w, "加密请求解析失败，请刷新页面后重试")
			return
		}
		envelope, err := ParseEnvelopeBody(body)
		if err != nil {
			response.Error(w, "加密请求解析失败，请刷新页面后重试")
			return
		}
		decrypted, err := m.Provider.DecryptEnvelope(envelope, r.Method, path)
		if err != nil {
			response.Error(w, "加密请求解析失败，请刷新页面后重试")
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(decrypted.Plaintext))
		r.ContentLength = int64(len(decrypted.Plaintext))
		r.Header.Set("Content-Type", "application/json")

		capture := &bytes.Buffer{}
		rec := &responseRecorder{header: w.Header(), status: 200, body: capture}
		next(rec, r)

		payload := capture.Bytes()
		if len(payload) == 0 {
			w.WriteHeader(rec.status)
			return
		}
		encryptedBody, err := EncryptResponse(decrypted.AESKey, payload, decrypted.KID, r.Method, path)
		if err != nil {
			response.Error(w, "响应加密失败")
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.Header().Set(headerEncryptResponse, "1")
		w.Header().Set(headerEncryptAlg, ResponseEnvelopeAlgorithm)
		w.Header().Set(headerEncryptKID, decrypted.KID)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encryptedBody)
	}
}

type responseRecorder struct {
	header http.Header
	status int
	body   *bytes.Buffer
}

func (r *responseRecorder) Header() http.Header { return r.header }

func (r *responseRecorder) Write(b []byte) (int, error) { return r.body.Write(b) }

func (r *responseRecorder) WriteHeader(statusCode int) { r.status = statusCode }

func SplitPaths(raw string) []string {
	out := []string{}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	return out
}

func ErrorEnvelope(msg string) []byte {
	raw, _ := json.Marshal(map[string]interface{}{
		"code": 500, "msg": msg, "success": false,
	})
	return raw
}
