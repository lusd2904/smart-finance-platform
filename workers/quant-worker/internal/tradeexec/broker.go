package tradeexec

import "context"

// Broker is the Longbridge trade/quote surface used by job handlers.
// Tests inject a fake; production uses the official openapi-go SDK.
type Broker interface {
	AccountBalance(ctx context.Context, creds Creds) (Account, error)
	Positions(ctx context.Context, creds Creds) ([]Position, error)
	TodayOrders(ctx context.Context, creds Creds) ([]Order, error)
	RealtimeQuotes(ctx context.Context, creds Creds, symbols []string, market string) ([]Quote, error)
	SubmitOrder(ctx context.Context, creds Creds, req SubmitReq) SubmitResult
}

func (a Account) NotConfiguredMessage() string {
	if a.Message != "" {
		return a.Message
	}
	return "长桥凭据未配置"
}
