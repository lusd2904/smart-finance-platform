package tradeexec

import (
	"errors"
	"strings"
	"testing"
)

func TestClassifyBrokerError401004IsNotSessionJWT(t *testing.T) {
	raw := errors.New(`longbridge: http 401 code=401004 message=access token invalid`)
	got := ClassifyBrokerError(raw)
	var br *BrokerRejectError
	if !errors.As(got, &br) {
		t.Fatalf("want BrokerRejectError, got %T %v", got, got)
	}
	if br.Code != BrokerTokenInvalidCode {
		t.Fatalf("code=%d", br.Code)
	}
	if strings.Contains(got.Error(), "请重新登录") || strings.Contains(got.Error(), "用户token已失效") {
		t.Fatalf("401004 must not look like platform JWT expiry: %s", got)
	}
	if !strings.Contains(got.Error(), "401004") || !strings.Contains(got.Error(), "OpenAPI") {
		t.Fatalf("msg=%s", got)
	}
	if IsSessionJWTError(got) {
		t.Fatal("classified broker reject must not be session JWT")
	}
}

func TestClassifyBrokerErrorLeavesSessionJWTAlone(t *testing.T) {
	raw := errors.New("用户token已失效，请重新登录")
	got := ClassifyBrokerError(raw)
	if got != raw {
		t.Fatalf("session JWT must stay unchanged: %v", got)
	}
	if IsBrokerTokenRejected(raw) {
		t.Fatal("platform JWT expiry must not be lumped with 401004")
	}
	if !IsSessionJWTError(raw) {
		t.Fatal("expected session JWT detector")
	}
}

func TestClassifyBrokerErrorIdempotent(t *testing.T) {
	first := ClassifyBrokerError(errors.New("401004 access token invalid"))
	second := ClassifyBrokerError(first)
	if first != second {
		t.Fatal("re-classify must keep the same error")
	}
}
