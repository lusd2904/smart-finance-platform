package ws

import (
	"encoding/json"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/quotes"
)

const (
	MinIntervalSeconds = 3
	MaxIntervalSeconds = 60
	DefaultInterval    = 15
)

type clientKind string

const (
	kindPing        clientKind = "ping"
	kindAuth        clientKind = "auth"
	kindSubscribe   clientKind = "subscribe"
	kindUnsubscribe clientKind = "unsubscribe"
	kindOther       clientKind = "other"
)

type clientFrame struct {
	Kind    clientKind
	Token   string
	Symbols []quotes.Pair
}

func NormalizeInterval(raw string) int {
	if strings.TrimSpace(raw) == "" {
		return DefaultInterval
	}
	n, err := strconv.Atoi(strings.TrimSpace(raw))
	if err != nil {
		return DefaultInterval
	}
	if n < MinIntervalSeconds {
		return MinIntervalSeconds
	}
	if n > MaxIntervalSeconds {
		return MaxIntervalSeconds
	}
	return n
}

func parseClientFrame(raw string) clientFrame {
	if raw == "ping" {
		return clientFrame{Kind: kindPing}
	}
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(raw), &data); err != nil {
		return clientFrame{Kind: kindOther}
	}
	kind := strings.ToLower(strings.TrimSpace(stringify(data["type"])))
	switch kind {
	case "auth":
		return clientFrame{Kind: kindAuth, Token: stringify(data["token"])}
	case "subscribe":
		return clientFrame{Kind: kindSubscribe, Symbols: quotes.ParseSubscribeSymbols(data["symbols"])}
	case "unsubscribe":
		if data["symbols"] != nil {
			return clientFrame{Kind: kindUnsubscribe, Symbols: quotes.ParseSubscribeSymbols(data["symbols"])}
		}
		return clientFrame{Kind: kindUnsubscribe, Symbols: []quotes.Pair{}}
	default:
		return clientFrame{Kind: kindOther}
	}
}

func tokenFromAuthFrame(raw string) string {
	frame := parseClientFrame(raw)
	if frame.Kind != kindAuth {
		return ""
	}
	return frame.Token
}

func stringify(v interface{}) string {
	if v == nil {
		return ""
	}
	s, _ := v.(string)
	return s
}
