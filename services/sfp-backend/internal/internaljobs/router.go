package internaljobs

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

var intelJobs = map[string]bool{
	"sentiment_collect": true, "sentiment_analyze": true, "watchlist_analyze": true,
	"daily_review": true, "req_send": true, "req_summarize": true, "stock_pick_run": true,
	"market_review": true, "ai_analyze": true, "ai_batch": true, "user_notice": true,
	"market_heat_collect": true, "symbol_content": true,
}

var quantJobs = map[string]bool{
	"factor_scan": true, "factor_qc": true, "strategy_run": true, "position_monitor": true,
	"daily_list_scan": true, "daily_list_open": true, "auto_trade_scan": true,
	"strategy_evaluate": true,
}

type Router struct {
	token     string
	intelURL  string
	quantURL  string
	client    *http.Client
}

func New(token, intelURL, quantURL string) *Router {
	return &Router{
		token:    strings.TrimSpace(token),
		intelURL: strings.TrimRight(strings.TrimSpace(intelURL), "/"),
		quantURL: strings.TrimRight(strings.TrimSpace(quantURL), "/"),
		client:   &http.Client{Timeout: 10 * time.Minute},
	}
}

func (r *Router) TokenConfigured() bool { return r != nil && r.token != "" }

func (r *Router) Authorize(header string) bool {
	return r != nil && r.token != "" && strings.TrimSpace(header) == r.token
}

type Request struct {
	Type    string                 `json:"type"`
	Payload map[string]interface{} `json:"payload"`
}

func (r *Router) Run(ctx context.Context, jobType string, payload map[string]interface{}) (map[string]interface{}, error) {
	jobType = strings.TrimSpace(jobType)
	if jobType == "" {
		return nil, fmt.Errorf("missing job type")
	}
	target := r.targetURL(jobType)
	if target == "" {
		return nil, fmt.Errorf("unknown job type: %s", jobType)
	}
	body, err := json.Marshal(Request{Type: jobType, Payload: payload})
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if r.token != "" {
		req.Header.Set("X-Internal-Token", r.token)
	}
	resp, err := r.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("delegate http %d: %s", resp.StatusCode, string(raw))
	}
	var out map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		return map[string]interface{}{"raw": string(raw)}, nil
	}
	return out, nil
}

func (r *Router) targetURL(jobType string) string {
	if intelJobs[jobType] {
		return r.intelURL + "/internal/jobs/run"
	}
	if quantJobs[jobType] {
		return r.quantURL + "/internal/jobs/run"
	}
	return ""
}

func (r *Router) IsKnown(jobType string) bool {
	return r.targetURL(jobType) != ""
}
