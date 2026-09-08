package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

func (s *Server) Register(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Username        string `json:"username"`
		Password        string `json:"password"`
		ConfirmPassword string `json:"confirmPassword"`
		Code            string `json:"code"`
		UUID            string `json:"uuid"`
	}
	if err := parseJSON(r, &body); err != nil {
		response.Warn(w, "注册失败")
		return
	}
	ctx := r.Context()
	if body.Password != body.ConfirmPassword {
		response.Warn(w, "两次输入的密码不一致")
		return
	}
	if !s.Auth.ConfigFlag(ctx, "sys.account.registerUser", false) {
		response.Warn(w, "注册程序已关闭，禁止注册")
		return
	}
	captchaEnabled := s.Auth.ConfigFlag(ctx, "sys.account.captchaEnabled", true)
	if captchaEnabled {
		if err := s.Auth.CheckCaptcha(ctx, body.UUID, body.Code); err != nil {
			response.Warn(w, err.Error())
			return
		}
	}
	userName := strings.TrimSpace(body.Username)
	if userName == "" {
		response.Warn(w, "用户名不能为空")
		return
	}
	if exists, _ := s.DB.UserNameExists(ctx, userName, 0); exists {
		response.Warn(w, "注册用户"+userName+"失败，登录账号已存在")
		return
	}
	hash, err := auth.HashPassword(body.Password)
	if err != nil {
		response.Error(w, "密码加密失败")
		return
	}
	payload := map[string]interface{}{
		"userName": userName, "nickName": userName, "password": body.Password,
	}
	if _, err := s.DB.InsertUser(ctx, payload, nil, nil, hash, userName); err != nil {
		response.Warn(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(ctx)
	response.SuccessModel(w, "注册成功", map[string]interface{}{"isSuccess": true, "message": "注册成功"})
}
