package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"testing"
	"time"
)

func TestDecryptFernetRoundTrip(t *testing.T) {
	plain := "longbridge-secret"
	source := "ci_test_secret_key_0123456789abcdef"
	token := mustEncrypt(t, plain, source)
	got, err := DecryptFernet(token, source)
	if err != nil {
		t.Fatal(err)
	}
	if got != plain {
		t.Fatalf("got %q", got)
	}
	if DecryptCredential(token, "", source) != plain {
		t.Fatal("DecryptCredential fallback to jwt secret")
	}
}

func mustEncrypt(t *testing.T, plain, source string) string {
	t.Helper()
	key := FernetKeyFromSecret(source)
	if len(key) != 32 {
		t.Fatalf("key len %d", len(key))
	}
	iv := make([]byte, 16)
	if _, err := rand.Read(iv); err != nil {
		t.Fatal(err)
	}
	block, err := aes.NewCipher(key[16:])
	if err != nil {
		t.Fatal(err)
	}
	pad := aes.BlockSize - len(plain)%aes.BlockSize
	pt := append([]byte(plain), make([]byte, pad)...)
	for i := range pt[len(plain):] {
		pt[len(plain)+i] = byte(pad)
	}
	ct := make([]byte, len(pt))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(ct, pt)
	body := make([]byte, 1+8+16+len(ct))
	body[0] = 0x80
	binary.BigEndian.PutUint64(body[1:9], uint64(time.Now().Unix()))
	copy(body[9:25], iv)
	copy(body[25:], ct)
	mac := hmac.New(sha256.New, key[:16])
	mac.Write(body)
	raw := append(body, mac.Sum(nil)...)
	return base64.URLEncoding.EncodeToString(raw)
}
