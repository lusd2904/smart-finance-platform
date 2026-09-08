package llm

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

const stockPickSystemPrompt = `你是二级市场选股助手。综合技术指标、当前舆情、以及仅在开盘时提供的大盘指数，给出克制的短线建议。
休市时没有实时指数，不要编造盘口，只根据指标和舆情判断。

严格输出 JSON（不要 markdown）：
{
  "stance": "偏多|偏空|中性",
  "recommendation": "买入|关注|观望|回避",
  "confidence": 0到100的整数,
  "summary": "综合研判，120字以内",
  "indicator_review": "指标解读，80字以内",
  "sentiment_review": "舆情解读，80字以内",
  "operation_advice": "操作建议，80字以内",
  "risk_warning": "主要风险，没有则填无"
}`

type StockPickResponse struct {
	OK     bool
	Result map[string]interface{}
	Raw    string
	Error  string
	Code   int
}

func (c *Client) AnalyzeStockPick(ctx context.Context, baseURL, apiKey, model string, item, contextData map[string]interface{}, temperature float64) StockPickResponse {
	user := buildStockPickUserPrompt(item, contextData)
	raw, code, err := c.chatJSON(ctx, baseURL, apiKey, model, stockPickSystemPrompt, user, temperature)
	if err != nil {
		return StockPickResponse{OK: false, Error: err.Error(), Code: code, Raw: raw}
	}
	parsed, perr := parseJSONObject(raw)
	if perr != nil {
		return StockPickResponse{OK: false, Error: perr.Error(), Raw: truncate(raw, 500)}
	}
	return StockPickResponse{OK: true, Result: parsed, Raw: raw}
}

func buildStockPickUserPrompt(item, contextData map[string]interface{}) string {
	lines := []string{
		fmt.Sprintf("标的：%v（%v / %v）", item["name"], item["symbol"], item["market"]),
		fmt.Sprintf("最新价：%v  涨跌：%v%%  因子分：%v  选股分：%v", item["price"], item["changePct"], item["factorScore"], item["pickScore"]),
		fmt.Sprintf("规则信号：%v  %v", item["signal"], item["reason"]),
		"",
		"【技术指标摘要】",
		truncateJSON(item["metrics"], 1800),
		"",
		"【市场环境】",
		truncateJSON(contextData["markets"], 1800),
		"",
		"【舆情综述】",
		fmt.Sprint(nestedString(contextData, "sentiment", "summary", "暂无")),
		"",
		"未开盘的市场已去掉实时指数。请按 JSON 输出。",
	}
	return strings.Join(lines, "\n")
}

const marketReviewSystemPrompt = `你是一名资深多市场策略分析师。用户会提供某一个市场（美股/港股/A股）收盘后的指数或代表股涨跌、涨跌家数、财经资讯和舆情。
请写一份克制、可执行的收盘复盘，不要喊单保证收益。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "title": "不超过24字的当日标题",
  "stance": "偏多|偏空|中性",
  "score": 0到100的整数（50为中性，越高越偏多）,
  "summary": "当日复盘，220字以内",
  "index_review": "对指数或代表股的解读，120字以内",
  "news_review": "对资讯的解读，没有则填'暂无有效资讯'",
  "sentiment_review": "对舆情的解读，没有则填'暂无相关舆情'",
  "outlook": "次日关注点，80字以内",
  "risk_warning": "主要风险，没有则填'无'",
  "key_points": ["要点1", "要点2", "要点3"]
}`

type MarketReviewResponse struct {
	OK     bool
	Result map[string]interface{}
	Raw    string
	Error  string
	Code   int
}

func (c *Client) AnalyzeMarketReview(ctx context.Context, baseURL, apiKey, model string, contextData map[string]interface{}, temperature float64) MarketReviewResponse {
	user := buildMarketReviewUserPrompt(contextData)
	raw, code, err := c.chatJSON(ctx, baseURL, apiKey, model, marketReviewSystemPrompt, user, temperature)
	if err != nil {
		return MarketReviewResponse{OK: false, Error: err.Error(), Code: code, Raw: raw}
	}
	parsed, perr := parseJSONObject(raw)
	if perr != nil {
		return MarketReviewResponse{OK: false, Error: perr.Error(), Raw: truncate(raw, 500)}
	}
	return MarketReviewResponse{OK: true, Result: parsed, Raw: raw}
}

func buildMarketReviewUserPrompt(contextData map[string]interface{}) string {
	lines := []string{
		fmt.Sprintf("市场：%v（%v）", contextData["marketLabel"], contextData["market"]),
		fmt.Sprintf("交易日：%v", contextData["tradeDate"]),
		fmt.Sprintf("上涨家数：%v  下跌家数：%v  样本：%v", contextData["upCount"], contextData["downCount"], contextData["sampleCount"]),
		"",
		"【指数 / 代表股】",
		truncateJSON(contextData["benchmarks"], 2500),
		"",
		"【财经资讯】",
	}
	news, _ := contextData["news"].([]map[string]interface{})
	if len(news) == 0 {
		lines = append(lines, "（暂无资讯）")
	} else {
		for i, item := range news {
			if i >= 8 {
				break
			}
			lines = append(lines, fmt.Sprintf("%d. %v | %v", i+1, item["headline"], truncate(fmt.Sprint(item["summary"]), 160)))
		}
	}
	lines = append(lines, "", "【相关舆情】")
	sentiment, _ := contextData["sentiment"].([]map[string]interface{})
	if len(sentiment) == 0 {
		lines = append(lines, "（暂无匹配舆情）")
	} else {
		for i, item := range sentiment {
			if i >= 8 {
				break
			}
			lines = append(lines, fmt.Sprintf("%d. [%v] %v", i+1, item["source"], item["title"]))
		}
	}
	lines = append(lines, "", "请按系统提示词要求的JSON格式输出收盘复盘。")
	return strings.Join(lines, "\n")
}

func (c *Client) chatJSON(ctx context.Context, baseURL, apiKey, model, system, user string, temperature float64) (string, int, error) {
	raw, err := c.ChatCompletion(ctx, baseURL, apiKey, model, system, nil, user, temperature)
	if err != nil {
		code := 0
		if strings.Contains(err.Error(), "429") {
			code = 429
		}
		return raw, code, err
	}
	return raw, 0, nil
}

func parseJSONObject(text string) (map[string]interface{}, error) {
	cleaned := strings.TrimSpace(text)
	if m := codeBlockRe.FindStringSubmatch(cleaned); len(m) > 1 {
		cleaned = m[1]
	} else {
		start, end := strings.Index(cleaned, "{"), strings.LastIndex(cleaned, "}")
		if start >= 0 && end > start {
			cleaned = cleaned[start : end+1]
		}
	}
	var out map[string]interface{}
	if err := json.Unmarshal([]byte(cleaned), &out); err != nil {
		return nil, fmt.Errorf("JSON解析失败: %w", err)
	}
	return out, nil
}

func truncateJSON(v interface{}, limit int) string {
	if v == nil {
		return "{}"
	}
	b, _ := json.Marshal(v)
	return truncate(string(b), limit)
}

func nestedString(m map[string]interface{}, keys ...string) string {
	cur := m
	for i, k := range keys {
		if i == len(keys)-1 {
			if cur == nil {
				return ""
			}
			if v, ok := cur[k]; ok {
				return fmt.Sprint(v)
			}
			return ""
		}
		next, ok := cur[k].(map[string]interface{})
		if !ok {
			return ""
		}
		cur = next
	}
	return ""
}

// RuleBasedMarketReview mirrors Python rule_based_market_review.
func RuleBasedMarketReview(contextData map[string]interface{}) map[string]interface{} {
	benches, _ := contextData["benchmarks"].([]map[string]interface{})
	changes := []float64{}
	for _, row := range benches {
		if chg, ok := row["changeRate"].(float64); ok {
			changes = append(changes, chg)
		}
	}
	avg := 0.0
	if len(changes) > 0 {
		sum := 0.0
		for _, c := range changes {
			sum += c
		}
		avg = sum / float64(len(changes))
	}
	up := intFrom(contextData["upCount"])
	down := intFrom(contextData["downCount"])
	sample := intFrom(contextData["sampleCount"])
	if sample < 1 {
		sample = 1
	}
	breadth := float64(up-down) / float64(sample)
	var stance string
	var score int
	switch {
	case avg > 0.4 && breadth >= 0:
		stance = "偏多"
		score = minInt(82, 55+int(avg*8)+int(breadth*10))
	case avg < -0.4 && breadth <= 0:
		stance = "偏空"
		score = maxInt(18, 45+int(avg*8)+int(breadth*10))
	default:
		stance = "中性"
		score = 50 + int(avg*6)
	}
	if score < 0 {
		score = 0
	}
	if score > 100 {
		score = 100
	}
	label := fmt.Sprint(contextData["marketLabel"])
	tradeDate := fmt.Sprint(contextData["tradeDate"])
	names := "代表标的数据不足"
	if len(benches) > 0 {
		parts := []string{}
		for i, b := range benches {
			if i >= 3 {
				break
			}
			parts = append(parts, fmt.Sprintf("%v %v", b["name"], b["changeText"]))
		}
		names = strings.Join(parts, "、")
	}
	newsCount := 0
	if news, ok := contextData["news"].([]map[string]interface{}); ok {
		newsCount = len(news)
	}
	sentCount := 0
	if sent, ok := contextData["sentiment"].([]map[string]interface{}); ok {
		sentCount = len(sent)
	}
	return map[string]interface{}{
		"title":             fmt.Sprintf("%s%s收盘复盘", label, tradeDate),
		"stance":            stance,
		"score":             score,
		"summary":           fmt.Sprintf("%s %s 收盘：代表组合均涨跌 %+.2f%%，样本上涨 %d / 下跌 %d。立场%s。资讯与舆情见下方，模型未配置时为指标兜底。", label, tradeDate, avg, up, down, stance),
		"index_review":      names,
		"news_review":       ifElse(newsCount == 0, "暂无有效资讯", fmt.Sprintf("收录 %d 条资讯", newsCount)),
		"sentiment_review":  ifElse(sentCount == 0, "暂无相关舆情", fmt.Sprintf("匹配 %d 条舆情", sentCount)),
		"outlook":           "关注量能能否持续以及隔夜外盘指引。",
		"risk_warning":      "规则兜底仅供参考，不构成投资建议。",
		"key_points":        []string{fmt.Sprintf("均涨跌%+.2f%%", avg), fmt.Sprintf("涨%d/跌%d", up, down), stance},
	}
}

func intFrom(v interface{}) int {
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	default:
		return 0
	}
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func ifElse(cond bool, a, b string) string {
	if cond {
		return a
	}
	return b
}
