package middleware

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/response"
)

type Middleware struct {
	Auth *auth.Authenticator
}

func (m *Middleware) RequirePerms(perms ...string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			user, err := m.Auth.Authenticate(r.Context(), r.Header.Get("Authorization"))
			if err != nil {
				response.Unauthorized(w, err.Error())
				return
			}
			if !user.HasPerm(perms...) {
				response.Forbidden(w, "该用户无此接口权限")
				return
			}
			next.ServeHTTP(w, r.WithContext(auth.WithUser(r.Context(), user)))
		})
	}
}

func (m *Middleware) OptionalUser(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.TrimSpace(r.Header.Get("Authorization")) != "" {
			user, err := m.Auth.Authenticate(r.Context(), r.Header.Get("Authorization"))
			if err == nil {
				r = r.WithContext(auth.WithUser(r.Context(), user))
			}
		}
		next.ServeHTTP(w, r)
	})
}
