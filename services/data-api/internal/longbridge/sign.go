package longbridge

import (
	"crypto/hmac"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

const signedHeaders = "authorization;x-api-key;x-timestamp"

// SignRequest builds the Longbridge legacy API-key HMAC-SHA256 header.
// canonical = METHOD|URI|PARAMS|authorization:TOKEN\nx-api-key:KEY\nx-timestamp:TS\n|authorization;x-api-key;x-timestamp|
// if body != "": canonical += sha1(body).hex
// sign_str = HMAC-SHA256| + sha1(canonical).hex
// signature = hmac_sha256(secret, sign_str).hex
func SignRequest(method, uri, query, body, appKey, accessToken, timestamp, appSecret string) string {
	method = strings.ToUpper(method)
	headerBlock := strings.Join([]string{
		"authorization:" + accessToken,
		"x-api-key:" + appKey,
		"x-timestamp:" + timestamp,
	}, "\n")
	canonical := method + "|" + uri + "|" + query + "|" + headerBlock + "\n|" + signedHeaders + "|"
	if body != "" {
		canonical += sha1Hex(body)
	}
	signStr := "HMAC-SHA256|" + sha1Hex(canonical)
	sig := hmacSHA256Hex(appSecret, signStr)
	return fmt.Sprintf("HMAC-SHA256 SignedHeaders=%s, Signature=%s", signedHeaders, sig)
}

func sha1Hex(s string) string {
	sum := sha1.Sum([]byte(s))
	return hex.EncodeToString(sum[:])
}

func hmacSHA256Hex(secret, data string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(data))
	return hex.EncodeToString(mac.Sum(nil))
}
