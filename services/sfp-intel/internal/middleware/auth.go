package middleware

import (
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/response"
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
