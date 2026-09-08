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

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/jobqueue"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/jobs"
)

type Router struct {
	token           string
	intelURL        string
	strategyEvalURL string
	enqueue         *jobqueue.Enqueuer
	client          *http.Client
}

func New(token, intelURL, strategyEvalURL string, enqueue *jobqueue.Enqueuer) *Router {
	return &Router{
		token:           strings.TrimSpace(token),
		intelURL:        strings.TrimRight(strings.TrimSpace(intelURL), "/"),
		strategyEvalURL: strings.TrimRight(strings.TrimSpace(strategyEvalURL), "/"),
		enqueue:         enqueue,
		client:          &http.Client{Timeout: 10 * time.Minute},
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
	if err := jobs.ValidateType(jobType); err != nil {
		return nil, err
	}
	if jobs.NativeGoWorkerTypes[jobType] {
		if r.enqueue == nil {
			return nil, fmt.Errorf("job queue unavailable")
		}
		job, err := r.enqueue.Enqueue(ctx, jobType, payload)
		if err != nil {
			return nil, err
		}
		return map[string]interface{}{
			"ok": true, "queued": true, "jobId": job.JobID, "queue": job.Queue, "type": jobType,
		}, nil
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
	if jobs.IntelBridgeTypes[jobType] {
		return r.intelURL + "/internal/jobs/run"
	}
	if jobs.QuantBridgeTypes[jobType] {
		if r.strategyEvalURL == "" {
			return ""
		}
		return r.strategyEvalURL + "/internal/jobs/run"
	}
	return ""
}

func (r *Router) IsKnown(jobType string) bool {
	return jobs.IsDelegatable(jobType)
}
