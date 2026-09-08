package handlers

import (
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

func (s *Server) TransportFrontendConfig(w http.ResponseWriter, r *http.Request) {
	data := s.Crypto.FrontendConfig(
		s.Config.TransportCryptoExcludePaths,
		s.Config.TransportCryptoEnabledPaths,
		s.Config.TransportCryptoRequiredPaths,
		s.Config.TransportCryptoMaxGetURLLength,
		s.Config.TransportCryptoFrontendConfigTTL,
	)
	response.Success(w, data)
}

func (s *Server) TransportPublicKey(w http.ResponseWriter, r *http.Request) {
	data, err := s.Crypto.PublicKeyPayload(s.Config.TransportCryptoPublicKeyTTL)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}
