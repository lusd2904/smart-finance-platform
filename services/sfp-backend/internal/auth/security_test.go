package auth

import (
	"context"
	"fmt"
	"testing"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
)

func testAuthService(t *testing.T) (*Service, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(mr.Close)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	return New(&config.Config{}, rdb, nil), mr
}

func TestCheckCaptchaOneTimeConsume(t *testing.T) {
	s, _ := testAuthService(t)
	ctx := context.Background()
	uuid := "captcha-once-uuid"
	if err := s.StoreCaptcha(ctx, uuid, "AB12"); err != nil {
		t.Fatal(err)
	}
	if err := s.CheckCaptcha(ctx, uuid, "AB12"); err != nil {
		t.Fatalf("first successful check should pass: %v", err)
	}
	if err := s.CheckCaptcha(ctx, uuid, "AB12"); err == nil {
		t.Fatal("captcha must be one-time; replay after success should fail")
	} else if err.Error() != "验证码已失效" {
		t.Fatalf("replay error = %v", err)
	}
}

func TestCheckCaptchaWrongCodeDoesNotConsume(t *testing.T) {
	s, _ := testAuthService(t)
	ctx := context.Background()
	uuid := "captcha-retry-uuid"
	if err := s.StoreCaptcha(ctx, uuid, "AB12"); err != nil {
		t.Fatal(err)
	}
	if err := s.CheckCaptcha(ctx, uuid, "WRONG"); err == nil {
		t.Fatal("wrong code should fail")
	} else if err.Error() != "验证码错误" {
		t.Fatalf("wrong-code error = %v", err)
	}
	if err := s.CheckCaptcha(ctx, uuid, "AB12"); err != nil {
		t.Fatalf("correct code after a failed attempt should still work: %v", err)
	}
}

func TestRecordLoginFailureUnifiesUnknownUserAndBadPassword(t *testing.T) {
	s, _ := testAuthService(t)
	ctx := context.Background()
	unknown := s.recordLoginFailure(ctx, "missing-user", "203.0.113.10")
	badPass := s.recordLoginFailure(ctx, "existing-user", "203.0.113.11")
	if unknown == nil || badPass == nil {
		t.Fatal("expected unified failure errors")
	}
	if unknown.Error() != loginFailMsg || badPass.Error() != loginFailMsg {
		t.Fatalf("messages must match: unknown=%q badPass=%q", unknown.Error(), badPass.Error())
	}
	if unknown.Error() == "用户不存在" || unknown.Error() == "密码错误" {
		t.Fatal("must not leak user-existence via distinct errors")
	}
}

func TestRecordLoginFailureLocksUsernameAndIP(t *testing.T) {
	s, _ := testAuthService(t)
	ctx := context.Background()

	var last error
	for i := 0; i < maxUserPasswordFails+1; i++ {
		last = s.recordLoginFailure(ctx, "locked-user", "203.0.113.20")
	}
	if last == nil || last.Error() != "10分钟内密码已输错超过5次，账号已锁定，请10分钟后再试" {
		t.Fatalf("username lock message = %v", last)
	}
	locked, msg := s.loginLocked(ctx, "locked-user", "198.51.100.1")
	if !locked || msg != "账号已锁定，请稍后再试" {
		t.Fatalf("username lock state locked=%v msg=%q", locked, msg)
	}

	s2, _ := testAuthService(t)
	for i := 0; i < maxIPLoginFails+1; i++ {
		last = s2.recordLoginFailure(ctx, fmt.Sprintf("spray-user-%d", i), "203.0.113.30")
	}
	if last == nil || last.Error() != "尝试次数过多，请稍后再试" {
		t.Fatalf("ip lock message = %v", last)
	}
	locked, msg = s2.loginLocked(ctx, "other-user", "203.0.113.30")
	if !locked || msg != "尝试次数过多，请稍后再试" {
		t.Fatalf("ip lock state locked=%v msg=%q", locked, msg)
	}
}
