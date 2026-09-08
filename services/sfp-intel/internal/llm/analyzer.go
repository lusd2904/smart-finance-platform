package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"
)

var (
	GatewayFailoverCodes = map[int]bool{502: true, 503: true, 524: true}
	codeBlockRe          = regexp.MustCompile("(?s)```(?:json)?\\s*(\\{.*?\\})\\s*```")
)

const systemPrompt = `你是一名资深宏观与市场策略分析师。用户会给你一批最新财经舆情快讯，请你综合分析这批舆情对全球主要股指的短期（1-3个交易日）影响。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "summary": "本批舆情的整体综述，150字以内",
  "us": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对美股三大指数（道琼斯、纳斯达克、标普500）的影响分析，100字以内"},
  "hk": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对港股恒生指数的影响分析，100字以内"},
  "a": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对A股上证指数、深证成指的影响分析，100字以内"},
  "risk_events": "值得重点关注的风险事件或催化剂，没有则填'无'"
}

评分标准：score为影响强度，正数利多负数利空，绝对值越大影响越强；0为中性。`

type NewsItem struct {
	Source  string
	Title   string
	Content string
	PubTime string
}

type MarketScore struct {
	Direction string  `json:"direction"`
	Score     float64 `json:"score"`
	Reason    string  `json:"reason"`
}

type AnalysisResult struct {
	Summary    string      `json:"summary"`
	US         MarketScore `json:"us"`
	HK         MarketScore `json:"hk"`
	A          MarketScore `json:"a"`
	RiskEvents string      `json:"risk_events"`
}

type AnalyzeResponse struct {
	OK         bool
	Result     *AnalysisResult
	Raw        string
	Error      string
	Code       int
	RetryAfter int
}

type Client struct {
	http *http.Client
}

func NewClient() *Client {
	return &Client{http: &http.Client{Timeout: 300 * time.Second}}
}

func (c *Client) Analyze(ctx context.Context, baseURL, apiKey, model string, news []NewsItem, temperature float64) AnalyzeResponse {
	url := strings.TrimRight(baseURL, "/")
	if !strings.HasSuffix(url, "/chat/completions") {
		url += "/chat/completions"
	}
	payload := map[string]interface{}{
		"model":       model,
		"temperature": temperature,
		"messages": []map[string]string{
			{"role": "system", "content": systemPrompt},
			{"role": "user", "content": buildUserPrompt(news)},
		},
	}
	body, _ := json.Marshal(payload)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return AnalyzeResponse{OK: false, Error: err.Error()}
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return AnalyzeResponse{OK: false, Error: err.Error()}
	}
	defer resp.Body.Close()
	rawBytes, _ := io.ReadAll(resp.Body)
	raw := string(rawBytes)
	if resp.StatusCode == 429 {
		retry := 60
		if v := resp.Header.Get("Retry-After"); v != "" {
			fmt.Sscanf(v, "%d", &retry)
		}
		return AnalyzeResponse{OK: false, Error: "模型调用过于频繁，请稍后再试", Code: 429, RetryAfter: retry}
	}
	if GatewayFailoverCodes[resp.StatusCode] {
		return AnalyzeResponse{OK: false, Error: fmt.Sprintf("网关错误 %d", resp.StatusCode), Code: resp.StatusCode, Raw: truncate(raw, 2000)}
	}
	if resp.StatusCode >= 400 {
		return AnalyzeResponse{OK: false, Error: fmt.Sprintf("http %d: %s", resp.StatusCode, truncate(raw, 500)), Code: resp.StatusCode, Raw: truncate(raw, 2000)}
	}
	var data struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(rawBytes, &data); err != nil {
		return AnalyzeResponse{OK: false, Error: "解析模型响应失败", Raw: truncate(raw, 2000)}
	}
	if len(data.Choices) == 0 {
		return AnalyzeResponse{OK: false, Error: "模型返回为空", Raw: truncate(raw, 2000)}
	}
	content := data.Choices[0].Message.Content
	parsed, err := parseJSON(content)
	if err != nil {
		return AnalyzeResponse{OK: false, Error: err.Error(), Raw: truncate(content, 2000)}
	}
	return AnalyzeResponse{OK: true, Result: parsed, Raw: truncate(content, 60000)}
}

func buildUserPrompt(news []NewsItem) string {
	var b strings.Builder
	b.WriteString("以下是最新采集的财经舆情快讯（含正文，请基于正文分析，不要只看标题）：\n\n")
	for i, n := range news {
		title := n.Title
		if len(title) > 200 {
			title = title[:200]
		}
		content := strings.TrimSpace(n.Content)
		if content == "" {
			content = title
		}
		if len(content) > 600 {
			content = content[:600]
		}
		fmt.Fprintf(&b, "%d. [%s][%s] %s\n", i+1, n.PubTime, n.Source, title)
		if content != "" && content != title {
			fmt.Fprintf(&b, "   正文: %s\n", content)
		}
	}
	b.WriteString("\n请按系统提示词要求的JSON格式输出分析结果。")
	return b.String()
}

func parseJSON(text string) (*AnalysisResult, error) {
	cleaned := strings.TrimSpace(text)
	if m := codeBlockRe.FindStringSubmatch(cleaned); len(m) > 1 {
		cleaned = m[1]
	} else {
		start, end := strings.Index(cleaned, "{"), strings.LastIndex(cleaned, "}")
		if start >= 0 && end > start {
			cleaned = cleaned[start : end+1]
		}
	}
	var out AnalysisResult
	if err := json.Unmarshal([]byte(cleaned), &out); err != nil {
		return nil, fmt.Errorf("JSON解析失败: %w", err)
	}
	return &out, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
