package handlers

import (
	"crypto/rand"
	"fmt"
	"net/http"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/captcha"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/menurouter"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

type Server struct {
	Auth *auth.Service
	DB   *store.DB
}

func (s *Server) Health(w http.ResponseWriter, _ *http.Request) {
	response.Success(w, map[string]string{"status": "ok"})
}

func (s *Server) CaptchaImage(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	captchaEnabled := s.Auth.ConfigFlag(ctx, "sys.account.captchaEnabled", true)
	registerEnabled := s.Auth.ConfigFlag(ctx, "sys.account.registerUser", false)
	uuid := generateUUID()
	img, answer, err := captcha.Generate()
	if err != nil {
		response.Error(w, "验证码生成失败")
		return
	}
	_ = s.Auth.StoreCaptcha(ctx, uuid, answer)
	response.SuccessModel(w, "操作成功", map[string]interface{}{
		"captchaEnabled": captchaEnabled,
		"registerEnabled": registerEnabled,
		"img":            img,
		"uuid":           uuid,
	})
}

func (s *Server) Login(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		response.Warn(w, "登录失败")
		return
	}
	ctx := r.Context()
	captchaEnabled := s.Auth.ConfigFlag(ctx, "sys.account.captchaEnabled", true)
	token, err := s.Auth.Login(ctx, r.FormValue("username"), r.FormValue("password"),
		r.FormValue("code"), r.FormValue("uuid"), captchaEnabled)
	if err != nil {
		response.Warn(w, err.Error())
		return
	}
	response.SuccessFlat(w, "登录成功", map[string]interface{}{"token": token})
}

func (s *Server) GetInfo(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	if user == nil {
		response.Unauthorized(w, "用户未登录，请先完成登录")
		return
	}
	p := user.Payload
	response.SuccessModel(w, "操作成功", map[string]interface{}{
		"permissions":        p.Permissions,
		"roles":              p.Roles,
		"user":               p.User,
		"isDefaultModifyPwd": p.IsDefaultModifyPwd,
		"isPasswordExpired":  p.IsPasswordExpired,
	})
}

func (s *Server) GetRouters(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	if user == nil {
		response.Unauthorized(w, "用户未登录，请先完成登录")
		return
	}
	bundle, err := s.DB.GetUserBundle(r.Context(), user.UserID)
	if err != nil || bundle == nil {
		response.Error(w, "获取路由失败")
		return
	}
	routers := menurouter.BuildRouters(bundle.Menus)
	response.Success(w, routers)
}

func (s *Server) Logout(w http.ResponseWriter, r *http.Request) {
	token, _ := parseBearer(r.Header.Get("Authorization"))
	_ = s.Auth.Logout(r.Context(), token)
	response.SuccessMsg(w, "退出成功")
}

func parseBearer(header string) (string, error) {
	return authParseBearer(header)
}

// avoid importing unexported - duplicate minimal parse
func authParseBearer(header string) (string, error) {
	h := header
	if len(h) > 7 && (h[:7] == "Bearer " || h[:7] == "bearer ") {
		return h[7:], nil
	}
	return h, nil
}

func generateUUID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}
