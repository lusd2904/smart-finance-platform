package tradeexec

import (
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"os"
	"strings"

	"github.com/fernet/fernet-go"
)

// DecryptOrRaw matches Python decrypt_or_raw: Fernet(SHA256(key)) then plaintext fallback.
func DecryptOrRaw(value, credentialKey, jwtSecret, appEnv string) string {
	if value == "" {
		return ""
	}
	plain, err := DecryptCredential(value, credentialKey, jwtSecret, appEnv)
	if err != nil {
		return value
	}
	return plain
}

func DecryptCredential(token, credentialKey, jwtSecret, appEnv string) (string, error) {
	if token == "" {
		return "", nil
	}
	source := strings.TrimSpace(credentialKey)
	if source == "" {
		if strings.EqualFold(appEnv, "prod") {
			return "", errors.New("CREDENTIAL_ENCRYPTION_KEY required in prod")
		}
		source = strings.TrimSpace(jwtSecret)
	}
	if source == "" {
		return "", errors.New("no credential encryption key")
	}
	sum := sha256.Sum256([]byte(source))
	key := base64.URLEncoding.EncodeToString(sum[:])
	k := fernet.MustDecodeKeys(key)
	msg := fernet.VerifyAndDecrypt([]byte(token), 0, k)
	if msg == nil {
		return "", errors.New("fernet decrypt failed")
	}
	return string(msg), nil
}

func EncryptionKeysFromEnv() (credentialKey, jwtSecret, appEnv string) {
	return strings.TrimSpace(os.Getenv("CREDENTIAL_ENCRYPTION_KEY")),
		strings.TrimSpace(firstEnv("JWT_SECRET_KEY", "JWT_SECRET")),
		strings.TrimSpace(firstEnv("APP_ENV", "APP_ENV"))
}

func firstEnv(keys ...string) string {
	for _, key := range keys {
		if v := strings.TrimSpace(os.Getenv(key)); v != "" {
			return v
		}
	}
	return ""
}
