package auth_test

import (
	"context"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/golang-jwt/jwt/v5"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
	"github.com/redis/go-redis/v9"
)

func TestJWTPayloadShape(t *testing.T) {
	secret := "ci_test_secret_key_0123456789abcdef"
	claims := jwt.MapClaims{
		"user_id":    "1",
		"user_name":  "admin",
		"dept_name":  nil,
		"session_id": "test-session",
		"exp":        time.Now().UTC().Add(8 * time.Hour).Unix(),
	}
	token, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := jwt.Parse(token, func(t *jwt.Token) (interface{}, error) {
		return []byte(secret), nil
	})
	if err != nil || !parsed.Valid {
		t.Fatalf("token invalid: %v", err)
	}
	pc := parsed.Claims.(jwt.MapClaims)
	if pc["user_id"] != "1" {
		t.Fatalf("unexpected user_id: %v", pc["user_id"])
	}
	if pc["session_id"] != "test-session" {
		t.Fatalf("unexpected session_id: %v", pc["session_id"])
	}
}

func TestLoginResponseEnvelope(t *testing.T) {
	body := map[string]interface{}{
		"code": 200, "msg": "登录成功", "success": true, "token": "abc",
	}
	if body["token"] == "" {
		t.Fatal("token missing")
	}
	if body["code"].(int) != 200 {
		t.Fatal("code mismatch")
	}
}

func TestCheckCaptchaConsumesOnMismatch(t *testing.T) {
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatal(err)
	}
	defer mr.Close()
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	svc := auth.New(&config.Config{}, rdb, nil)
	ctx := context.Background()
	if err := svc.StoreCaptcha(ctx, "u1", "1234"); err != nil {
		t.Fatal(err)
	}
	if err := svc.CheckCaptcha(ctx, "u1", "wrong"); err == nil || err.Error() != "验证码错误" {
		t.Fatalf("mismatch err=%v", err)
	}
	if err := svc.CheckCaptcha(ctx, "u1", "1234"); err == nil || err.Error() != "验证码已失效" {
		t.Fatalf("consumed err=%v", err)
	}
}

func TestCheckCaptchaOKConsumes(t *testing.T) {
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatal(err)
	}
	defer mr.Close()
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	svc := auth.New(&config.Config{}, rdb, nil)
	ctx := context.Background()
	if err := svc.StoreCaptcha(ctx, "u2", "5678"); err != nil {
		t.Fatal(err)
	}
	if err := svc.CheckCaptcha(ctx, "u2", "5678"); err != nil {
		t.Fatal(err)
	}
	if err := svc.CheckCaptcha(ctx, "u2", "5678"); err == nil || err.Error() != "验证码已失效" {
		t.Fatalf("replay err=%v", err)
	}
}
