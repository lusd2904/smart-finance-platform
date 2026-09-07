package delegate

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type PythonClient struct {
	url    string
	token  string
	client *http.Client
}

func New(url, token string) *PythonClient {
	return &PythonClient{
		url:    url,
		token:  token,
		client: &http.Client{Timeout: 10 * time.Minute},
	}
}

func (p *PythonClient) Run(ctx context.Context, jobType string, payload map[string]interface{}) (map[string]interface{}, error) {
	if p.url == "" {
		return nil, fmt.Errorf("PYTHON_DELEGATE_URL is not configured")
	}
	body, err := json.Marshal(map[string]interface{}{
		"type":    jobType,
		"payload": payload,
	})
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, p.url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if p.token != "" {
		req.Header.Set("X-Internal-Token", p.token)
	}
	resp, err := p.client.Do(req)
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
