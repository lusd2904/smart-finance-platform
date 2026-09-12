package tradeexec

import (
	"errors"
	"strings"
)

// Longbridge OpenAPI rejects an invalid/paper access token with HTTP 401
// business code 401004 ("access token invalid"). That is the broker refusing
// the Longbridge token — not our platform JWT expiring.
const (
	BrokerTokenInvalidCode = 401004
	BrokerTokenInvalidMsg  = "长桥 OpenAPI 拒绝了当前 Access Token（401004）：券商不接受该纸交易账户 token，或该 token 对该接口无效。这不是平台登录过期，请勿刷新本站 JWT。"
)

// BrokerRejectError is a hard broker-auth failure. Positions/tearsheet must
// surface this as empty/error — do not invent holdings.
type BrokerRejectError struct {
	Code    int
	Message string
	Cause   error
}

func (e *BrokerRejectError) Error() string {
	if e == nil {
		return ""
	}
	if e.Message != "" {
		return e.Message
	}
	return BrokerTokenInvalidMsg
}

func (e *BrokerRejectError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Cause
}

// ClassifyBrokerError remaps Longbridge 401004 / "access token invalid" to a
// BrokerRejectError. Session JWT copy ("用户token已失效，请重新登录") is left
// untouched — DecryptOrRaw only Fernet-decrypts stored credentials and is not
// applied as JWT.Parse on the Longbridge token.
func ClassifyBrokerError(err error) error {
	if err == nil {
		return nil
	}
	var already *BrokerRejectError
	if errors.As(err, &already) {
		return already
	}
	if !IsBrokerTokenRejected(err) {
		return err
	}
	return &BrokerRejectError{
		Code:    BrokerTokenInvalidCode,
		Message: BrokerTokenInvalidMsg,
		Cause:   err,
	}
}

func IsBrokerTokenRejected(err error) bool {
	if err == nil {
		return false
	}
	var br *BrokerRejectError
	if errors.As(err, &br) && br != nil && br.Code == BrokerTokenInvalidCode {
		return true
	}
	text := err.Error()
	if strings.Contains(text, "401004") {
		return true
	}
	lower := strings.ToLower(text)
	return strings.Contains(lower, "access token invalid")
}

func IsSessionJWTError(err error) bool {
	if err == nil {
		return false
	}
	text := err.Error()
	return strings.Contains(text, "请重新登录") || strings.Contains(text, "用户token已失效")
}
