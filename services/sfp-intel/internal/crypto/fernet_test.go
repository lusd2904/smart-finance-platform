package crypto

import "testing"

func TestEncryptDecryptRoundTrip(t *testing.T) {
	secret := "test-credential-key"
	plain := "sk-test-api-key"
	enc := EncryptCredential(plain, secret, "")
	dec := DecryptCredential(enc, secret, "")
	if dec != plain {
		t.Fatalf("round trip failed: %q -> %q", plain, dec)
	}
}
