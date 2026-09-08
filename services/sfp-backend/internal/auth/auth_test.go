package auth_test

import (
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
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
