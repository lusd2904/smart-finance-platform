package transportcrypto

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"strings"
)

const (
	EnvelopeVersion           = "1"
	ResponseEnvelopeAlgorithm = "AES_256_GCM"
)

type KeyPair struct {
	KID        string
	PrivatePEM string
	PublicPEM  string
}

type Provider struct {
	current string
	pairs   map[string]KeyPair
	enabled bool
	mode    string
	algo    string
}

func NewProvider(enabled bool, mode, algo, kid, privatePEM, publicPEM, legacyJSON string) (*Provider, error) {
	p := &Provider{
		current: kid,
		enabled: enabled,
		mode:    mode,
		algo:    algo,
		pairs:   map[string]KeyPair{},
	}
	if !enabled || mode == "off" {
		return p, nil
	}
	priv := normalizePEM(privatePEM)
	pub := normalizePEM(publicPEM)
	if priv == "" || pub == "" {
		return nil, fmt.Errorf("transport crypto keys are required when enabled")
	}
	p.pairs[kid] = KeyPair{KID: kid, PrivatePEM: priv, PublicPEM: pub}
	if legacyJSON != "" && legacyJSON != "[]" {
		var items []map[string]string
		if err := json.Unmarshal([]byte(legacyJSON), &items); err != nil {
			return nil, fmt.Errorf("invalid TRANSPORT_CRYPTO_LEGACY_KEY_PAIRS: %w", err)
		}
		for _, item := range items {
			lkid := strings.TrimSpace(item["kid"])
			lpriv := normalizePEM(item["privateKey"])
			if lkid == "" || lpriv == "" {
				return nil, fmt.Errorf("legacy key pair must include kid and privateKey")
			}
			lpub := normalizePEM(item["publicKey"])
			if lpub == "" {
				block, _ := pem.Decode([]byte(lpriv))
				if block == nil {
					return nil, fmt.Errorf("invalid legacy private key")
				}
				key, err := x509.ParsePKCS8PrivateKey(block.Bytes)
				if err != nil {
					key, err = x509.ParsePKCS1PrivateKey(block.Bytes)
				}
				if err != nil {
					return nil, err
				}
				rsaKey, ok := key.(*rsa.PrivateKey)
				if !ok {
					return nil, fmt.Errorf("legacy key is not RSA")
				}
				pubBytes, err := x509.MarshalPKIXPublicKey(&rsaKey.PublicKey)
				if err != nil {
					return nil, err
				}
				lpub = string(pem.EncodeToMemory(&pem.Block{
					Type:  "PUBLIC KEY",
					Bytes: pubBytes,
				}))
			}
			p.pairs[lkid] = KeyPair{KID: lkid, PrivatePEM: lpriv, PublicPEM: lpub}
		}
	}
	return p, nil
}

func (p *Provider) Enabled() bool { return p.enabled && p.mode != "off" }

func (p *Provider) Mode() string { return p.mode }

func normalizePEM(v string) string {
	return strings.TrimSpace(strings.ReplaceAll(v, "\\n", "\n"))
}

func urlsafeB64Encode(data []byte) string {
	return strings.TrimRight(base64.URLEncoding.EncodeToString(data), "=")
}

func urlsafeB64Decode(data string) ([]byte, error) {
	pad := (4 - len(data)%4) % 4
	return base64.URLEncoding.DecodeString(data + strings.Repeat("=", pad))
}

func buildAADBytes(aad map[string]string) []byte {
	raw, _ := json.Marshal(aad)
	return raw
}

type DecryptedEnvelope struct {
	KID       string
	AESKey    []byte
	AAD       map[string]string
	Plaintext []byte
}

func (p *Provider) DecryptEnvelope(envelope map[string]interface{}, method, path string) (*DecryptedEnvelope, error) {
	if p.algo != "" && envelope["alg"] != nil && fmt.Sprint(envelope["alg"]) != p.algo {
		return nil, fmt.Errorf("unsupported algorithm")
	}
	if fmt.Sprint(envelope["v"]) != EnvelopeVersion {
		return nil, fmt.Errorf("unsupported envelope version")
	}
	for _, field := range []string{"kid", "ts", "nonce", "ek", "iv", "ct", "aad"} {
		if envelope[field] == nil || fmt.Sprint(envelope[field]) == "" {
			return nil, fmt.Errorf("missing field %s", field)
		}
	}
	kid := fmt.Sprint(envelope["kid"])
	pair, ok := p.pairs[kid]
	if !ok {
		return nil, fmt.Errorf("unknown kid")
	}
	aadRaw, ok := envelope["aad"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid aad")
	}
	aad := map[string]string{
		"method": strings.ToUpper(fmt.Sprint(aadRaw["method"])),
		"path":   fmt.Sprint(aadRaw["path"]),
	}
	if aad["method"] != strings.ToUpper(method) || aad["path"] != path {
		return nil, fmt.Errorf("aad mismatch")
	}
	aesKey, err := decryptRequestKey(pair.PrivatePEM, fmt.Sprint(envelope["ek"]))
	if err != nil {
		return nil, err
	}
	iv, err := urlsafeB64Decode(fmt.Sprint(envelope["iv"]))
	if err != nil {
		return nil, err
	}
	ct, err := urlsafeB64Decode(fmt.Sprint(envelope["ct"]))
	if err != nil {
		return nil, err
	}
	block, err := aes.NewCipher(aesKey)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	plaintext, err := gcm.Open(nil, iv, ct, buildAADBytes(aad))
	if err != nil {
		return nil, err
	}
	return &DecryptedEnvelope{KID: kid, AESKey: aesKey, AAD: aad, Plaintext: plaintext}, nil
}

func decryptRequestKey(privatePEM, ek string) ([]byte, error) {
	block, _ := pem.Decode([]byte(privatePEM))
	if block == nil {
		return nil, fmt.Errorf("invalid private key")
	}
	key, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		key, err = x509.ParsePKCS1PrivateKey(block.Bytes)
	}
	if err != nil {
		return nil, err
	}
	rsaKey, ok := key.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("not RSA key")
	}
	enc, err := urlsafeB64Decode(ek)
	if err != nil {
		return nil, err
	}
	return rsa.DecryptOAEP(sha256.New(), rand.Reader, rsaKey, enc, nil)
}

func EncryptResponse(aesKey []byte, payload []byte, kid, method, path string) ([]byte, error) {
	iv := make([]byte, 12)
	if _, err := rand.Read(iv); err != nil {
		return nil, err
	}
	aad := map[string]string{"method": strings.ToUpper(method), "path": path, "direction": "response"}
	block, err := aes.NewCipher(aesKey)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	ct := gcm.Seal(nil, iv, payload, buildAADBytes(aad))
	out := map[string]interface{}{
		"v":   EnvelopeVersion,
		"kid": kid,
		"alg": ResponseEnvelopeAlgorithm,
		"aad": aad,
		"iv":  urlsafeB64Encode(iv),
		"ct":  urlsafeB64Encode(ct),
	}
	return json.Marshal(out)
}

func ParseEnvelopeBody(body []byte) (map[string]interface{}, error) {
	var envelope map[string]interface{}
	if err := json.Unmarshal(body, &envelope); err != nil {
		return nil, err
	}
	return envelope, nil
}

func CaptureResponse(buf *bytes.Buffer) func([]byte) (int, error) {
	return buf.Write
}
