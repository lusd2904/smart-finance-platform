package tradeexec

import (
	"crypto/sha256"
	"encoding/base64"
	"testing"

	"github.com/fernet/fernet-go"
)

func TestDecryptOrRawRoundTrip(t *testing.T) {
	source := "ci_test_secret_key_0123456789abcdef"
	sum := sha256.Sum256([]byte(source))
	key := base64.URLEncoding.EncodeToString(sum[:])
	k := fernet.MustDecodeKeys(key)
	tok, err := fernet.EncryptAndSign([]byte("paper-token-xyz"), k[0])
	if err != nil {
		t.Fatal(err)
	}
	got := DecryptOrRaw(string(tok), source, "unused", "dev")
	if got != "paper-token-xyz" {
		t.Fatalf("got %q", got)
	}
	if DecryptOrRaw("plain-legacy", "wrong-key", "", "dev") != "plain-legacy" {
		t.Fatal("legacy plaintext should pass through")
	}
	if got := DecryptOrRaw(string(tok), "wrong-key-xxxxxxxxxxxxxxxxxxxx", "", "dev"); got != "" {
		t.Fatalf("fernet+wrong key in dev must not return ciphertext, got %q", got)
	}
	if got := DecryptOrRaw(string(tok), "wrong-key-xxxxxxxxxxxxxxxxxxxx", "jwt", "prod"); got != "" {
		t.Fatalf("fernet+wrong key in prod must not return ciphertext, got %q", got)
	}
}

func TestProdRequiresDedicatedKey(t *testing.T) {
	_, err := DecryptCredential("gAAAAA", "", "jwt-only", "prod")
	if err == nil {
		t.Fatal("prod must require CREDENTIAL_ENCRYPTION_KEY")
	}
}
