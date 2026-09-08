package transportcrypto

import (
	"fmt"
	"time"
)

func (p *Provider) FrontendConfig(excludePaths, enabledPaths, requiredPaths string, maxGetURL int, configTTL int) map[string]interface{} {
	active := p.Enabled()
	return map[string]interface{}{
		"transportCryptoEnabled":      p.enabled,
		"transportCryptoMode":       p.mode,
		"transportCryptoActive":     active,
		"envelopeVersion":           EnvelopeVersion,
		"publicKeyUrl":              "/transport/crypto/public-key",
		"requestEnvelopeAlgorithm":  p.algo,
		"responseEnvelopeAlgorithm": ResponseEnvelopeAlgorithm,
		"enabledPaths":              SplitPaths(enabledPaths),
		"requiredPaths":             SplitPaths(requiredPaths),
		"excludePaths":              SplitPaths(excludePaths),
		"maxEncryptedGetUrlLength":  maxGetURL,
		"configExpireAt":            int(time.Now().Unix()) + configTTL,
	}
}

func (p *Provider) PublicKeyPayload(ttl int) (map[string]interface{}, error) {
	if !p.Enabled() {
		return map[string]interface{}{
			"kid": p.current, "envelopeVersion": EnvelopeVersion, "alg": p.algo,
			"publicKey": "", "supportedKids": []string{}, "expireAt": int(time.Now().Unix()) + ttl,
		}, nil
	}
	pair, ok := p.pairs[p.current]
	if !ok {
		return nil, fmt.Errorf("transport crypto key not configured")
	}
	kids := make([]string, 0, len(p.pairs))
	for kid := range p.pairs {
		kids = append(kids, kid)
	}
	return map[string]interface{}{
		"kid": pair.KID, "envelopeVersion": EnvelopeVersion, "alg": p.algo,
		"publicKey": pair.PublicPEM, "supportedKids": kids,
		"expireAt": int(time.Now().Unix()) + ttl,
	}, nil
}

func (p *Provider) CurrentKID() string { return p.current }
