package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"strings"
	"time"
)

func FernetKeyFromSecret(source string) []byte {
	sum := sha256.Sum256([]byte(source))
	return sum[:]
}

func DecryptFernet(token, source string) (string, error) {
	if token == "" || source == "" {
		return token, nil
	}
	key := FernetKeyFromSecret(source)
	if len(key) != 32 {
		return "", fmt.Errorf("fernet key length %d", len(key))
	}
	raw, err := base64.URLEncoding.DecodeString(padB64(token))
	if err != nil {
		raw, err = base64.RawURLEncoding.DecodeString(token)
		if err != nil {
			return "", err
		}
	}
	if len(raw) < 1+8+16+32 {
		return "", fmt.Errorf("token too short")
	}
	if raw[0] != 0x80 {
		return "", fmt.Errorf("unsupported fernet version")
	}
	signing := key[:16]
	encKey := key[16:]
	mac := raw[len(raw)-32:]
	body := raw[:len(raw)-32]
	h := hmac.New(sha256.New, signing)
	h.Write(body)
	if !hmac.Equal(h.Sum(nil), mac) {
		return "", fmt.Errorf("fernet hmac mismatch")
	}
	iv := body[9:25]
	ct := body[25:]
	block, err := aes.NewCipher(encKey)
	if err != nil {
		return "", err
	}
	if len(ct)%aes.BlockSize != 0 {
		return "", fmt.Errorf("ciphertext not block-aligned")
	}
	pt := make([]byte, len(ct))
	cipher.NewCBCDecrypter(block, iv).CryptBlocks(pt, ct)
	pt, err = pkcs7Unpad(pt)
	if err != nil {
		return "", err
	}
	return string(pt), nil
}

func DecryptCredential(token, credentialKey, jwtSecret string) string {
	if token == "" {
		return token
	}
	source := strings.TrimSpace(credentialKey)
	if source == "" {
		source = jwtSecret
	}
	plain, err := DecryptFernet(token, source)
	if err != nil {
		return token
	}
	return plain
}

func padB64(s string) string {
	if m := len(s) % 4; m != 0 {
		return s + strings.Repeat("=", 4-m)
	}
	return s
}

func pkcs7Unpad(b []byte) ([]byte, error) {
	if len(b) == 0 {
		return nil, fmt.Errorf("empty")
	}
	n := int(b[len(b)-1])
	if n == 0 || n > len(b) {
		return nil, fmt.Errorf("bad padding")
	}
	for i := 0; i < n; i++ {
		if b[len(b)-1-i] != byte(n) {
			return nil, fmt.Errorf("bad padding")
		}
	}
	return b[:len(b)-n], nil
}

func EncryptFernet(plain, source string) (string, error) {
	key := FernetKeyFromSecret(source)
	if len(key) != 32 {
		return "", fmt.Errorf("fernet key length %d", len(key))
	}
	signing := key[:16]
	encKey := key[16:]
	iv := make([]byte, aes.BlockSize)
	if _, err := rand.Read(iv); err != nil {
		return "", err
	}
	block, err := aes.NewCipher(encKey)
	if err != nil {
		return "", err
	}
	pt := pkcs7Pad([]byte(plain), aes.BlockSize)
	ct := make([]byte, len(pt))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(ct, pt)
	buf := make([]byte, 1+8+aes.BlockSize+len(ct))
	buf[0] = 0x80
	binary.BigEndian.PutUint64(buf[1:9], uint64(time.Now().Unix()))
	copy(buf[9:9+aes.BlockSize], iv)
	copy(buf[9+aes.BlockSize:], ct)
	mac := hmac.New(sha256.New, signing)
	mac.Write(buf)
	sum := mac.Sum(nil)
	out := append(buf, sum...)
	return base64.URLEncoding.EncodeToString(out), nil
}

func pkcs7Pad(b []byte, block int) []byte {
	n := block - (len(b) % block)
	if n == 0 {
		n = block
	}
	out := make([]byte, len(b)+n)
	copy(out, b)
	for i := len(b); i < len(out); i++ {
		out[i] = byte(n)
	}
	return out
}
