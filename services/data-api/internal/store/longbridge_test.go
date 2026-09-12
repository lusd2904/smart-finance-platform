package store

import (
	"strings"
	"testing"

	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

func TestEncryptCredentialProdRequiresKey(t *testing.T) {
	for _, env := range []string{"prod", "production", "PROD", "Production"} {
		got, err := encryptCredential("sample-credential", "", "jwt-only-fallback", env)
		if err == nil {
			t.Fatalf("env %q must refuse plaintext write without CREDENTIAL_ENCRYPTION_KEY", env)
		}
		if got != "" {
			t.Fatalf("env %q must not return ciphertext or plaintext on refusal, got %q", env, got)
		}
		if !strings.Contains(err.Error(), "CREDENTIAL_ENCRYPTION_KEY") {
			t.Fatalf("env %q: unexpected error %v", env, err)
		}
	}
}

func TestEncryptCredentialDevFallsBackToJWT(t *testing.T) {
	got, err := encryptCredential("sample-credential", "", "jwt-fallback-key", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if got == "" || got == "sample-credential" {
		t.Fatalf("dev should encrypt with jwt fallback, got %q", got)
	}
	plain := tradeexec.DecryptOrRaw(got, "", "jwt-fallback-key", "dev")
	if plain != "sample-credential" {
		t.Fatalf("roundtrip got %q", plain)
	}
}

func TestEncryptCredentialProdWithDedicatedKey(t *testing.T) {
	got, err := encryptCredential("sample-credential", "dedicated-cred-key", "jwt-unused", "prod")
	if err != nil {
		t.Fatal(err)
	}
	if got == "" || got == "sample-credential" {
		t.Fatal("prod with dedicated key must not store plaintext")
	}
	plain := tradeexec.DecryptOrRaw(got, "dedicated-cred-key", "jwt-unused", "prod")
	if plain != "sample-credential" {
		t.Fatalf("roundtrip got %q", plain)
	}
}

func TestMaskLongbridgePublicFieldsIncludesAppKey(t *testing.T) {
	cfg := LongbridgeConfig{
		AppKey:      "appkey-abcdef",
		AppSecret:   "secret-abcdef",
		AccessToken: "token-abcdef",
	}
	maskLongbridgePublicFields(&cfg)
	if cfg.AppKey != "****cdef" {
		t.Fatalf("AppKey mask = %q", cfg.AppKey)
	}
	if cfg.AppSecret != "****cdef" {
		t.Fatalf("AppSecret mask = %q", cfg.AppSecret)
	}
	if cfg.AccessToken != "****cdef" {
		t.Fatalf("AccessToken mask = %q", cfg.AccessToken)
	}
}

func TestKeepExistingCredential(t *testing.T) {
	if !keepExistingCredential("") || !keepExistingCredential("****cdef") {
		t.Fatal("empty or masked values must keep the stored credential")
	}
	if keepExistingCredential("new-plain-value") {
		t.Fatal("plaintext replacement must be written")
	}
}
