package internaljobs

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client calls Go sfp-backend POST /internal/jobs/run (INTERNAL_JOBS_URL).
type Client struct {
	url    string
	token  string
	client *http.Client
}

func New(url, token string) *Client {
	return &Client{
		url:    url,
		token:  token,
		client: &http.Client{Timeout: 10 * time.Minute},
	}
}

func (c *Client) Run(ctx context.Context, jobType string, payload map[string]interface{}) (map[string]interface{}, error) {
	if c.url == "" {
		return nil, fmt.Errorf("INTERNAL_JOBS_URL is not configured")
	}
	body, err := json.Marshal(map[string]interface{}{
		"type":    jobType,
		"payload": payload,
	})
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		req.Header.Set("X-Internal-Token", c.token)
	}
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("internal jobs http %d: %s", resp.StatusCode, string(raw))
	}
	var out map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		return map[string]interface{}{"raw": string(raw)}, nil
	}
	return out, nil
}
