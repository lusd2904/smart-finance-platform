package llm

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type StreamRequest struct {
	BaseURL     string
	APIKey      string
	Model       string
	Temperature float64
	MaxTokens   int
	Messages    []ChatMessage
	Reasoning   bool
}

type StreamEvent struct {
	Type      string                 `json:"type"`
	SessionID string                 `json:"session_id,omitempty"`
	RunID     string                 `json:"run_id,omitempty"`
	Content   string                 `json:"content,omitempty"`
	Error     string                 `json:"error,omitempty"`
	Metrics   map[string]interface{} `json:"metrics,omitempty"`
}

type StreamResult struct {
	Content   string
	Reasoning string
	Metrics   map[string]interface{}
}

func (c *Client) StreamChat(ctx context.Context, req StreamRequest, runID string, emit func(StreamEvent) error) (*StreamResult, error) {
	url := strings.TrimRight(req.BaseURL, "/")
	if !strings.HasSuffix(url, "/chat/completions") {
		url += "/chat/completions"
	}
	payload := map[string]interface{}{
		"model":       req.Model,
		"temperature": req.Temperature,
		"stream":      true,
		"messages":    req.Messages,
	}
	if req.MaxTokens > 0 {
		payload["max_tokens"] = req.MaxTokens
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Authorization", "Bearer "+req.APIKey)
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "text/event-stream")

	resp, err := c.http.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 429 {
		return nil, fmt.Errorf("模型调用过于频繁，请稍后再试")
	}
	if GatewayFailoverCodes[resp.StatusCode] {
		return nil, fmt.Errorf("网关错误 %d", resp.StatusCode)
	}
	if resp.StatusCode >= 400 {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 500))
		return nil, fmt.Errorf("http %d: %s", resp.StatusCode, truncate(string(raw), 500))
	}

	if err := emit(StreamEvent{Type: "run_info", RunID: runID}); err != nil {
		return nil, err
	}

	result := &StreamResult{}
	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		default:
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, ":") {
			continue
		}
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
		if data == "[DONE]" {
			break
		}
		var chunk streamChunk
		if err := json.Unmarshal([]byte(data), &chunk); err != nil {
			continue
		}
		if chunk.Usage != nil {
			result.Metrics = usageMetrics(chunk.Usage)
		}
		if len(chunk.Choices) == 0 {
			continue
		}
		delta := chunk.Choices[0].Delta
		if delta.ReasoningContent != "" && req.Reasoning {
			result.Reasoning += delta.ReasoningContent
			if err := emit(StreamEvent{Type: "reasoning", Content: delta.ReasoningContent}); err != nil {
				return result, err
			}
		}
		if delta.Content != "" {
			result.Content += delta.Content
			if err := emit(StreamEvent{Type: "content", Content: delta.Content}); err != nil {
				return result, err
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return result, err
	}
	if result.Metrics != nil {
		_ = emit(StreamEvent{Type: "metrics", Metrics: result.Metrics})
	}
	return result, nil
}

func (c *Client) CompleteChat(ctx context.Context, req StreamRequest) (string, error) {
	url := strings.TrimRight(req.BaseURL, "/")
	if !strings.HasSuffix(url, "/chat/completions") {
		url += "/chat/completions"
	}
	payload := map[string]interface{}{
		"model":       req.Model,
		"temperature": req.Temperature,
		"messages":    req.Messages,
	}
	if req.MaxTokens > 0 {
		payload["max_tokens"] = req.MaxTokens
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	httpReq.Header.Set("Authorization", "Bearer "+req.APIKey)
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(httpReq)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	rawBytes, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("http %d: %s", resp.StatusCode, truncate(string(rawBytes), 500))
	}
	var data struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(rawBytes, &data); err != nil {
		return "", fmt.Errorf("解析模型响应失败")
	}
	if len(data.Choices) == 0 {
		return "", fmt.Errorf("模型返回为空")
	}
	return data.Choices[0].Message.Content, nil
}

type streamChunk struct {
	Choices []struct {
		Delta struct {
			Content          string `json:"content"`
			ReasoningContent string `json:"reasoning_content"`
		} `json:"delta"`
	} `json:"choices"`
	Usage *usagePayload `json:"usage"`
}

type usagePayload struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

func usageMetrics(u *usagePayload) map[string]interface{} {
	if u == nil {
		return nil
	}
	return map[string]interface{}{
		"inputTokens":  u.PromptTokens,
		"outputTokens": u.CompletionTokens,
		"totalTokens":  u.TotalTokens,
	}
}

func NewStreamClient(timeout time.Duration) *Client {
	if timeout <= 0 {
		timeout = 300 * time.Second
	}
	return &Client{http: &http.Client{Timeout: timeout}}
}
