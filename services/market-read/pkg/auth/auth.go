package auth

import iauth "github.com/lusd2904/smart-finance-platform/services/market-read/internal/auth"

type User = iauth.User
type Authenticator = iauth.Authenticator

var (
	WithUser = iauth.WithUser
	UserFrom = iauth.UserFrom
	New      = iauth.New
)
