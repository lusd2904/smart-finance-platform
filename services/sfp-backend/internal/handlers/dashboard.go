package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

func (s *Server) DashboardSummary(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	if user == nil {
		response.Unauthorized(w, "用户未登录，请先完成登录")
		return
	}
	refresh := strings.EqualFold(r.URL.Query().Get("refresh"), "true")
	data, err := s.Dashboard.Summary(r.Context(), user.UserID, user.Permissions, refresh)
	if err != nil {
		response.Error(w, "获取工作台总览失败")
		return
	}
	response.Success(w, data)
}
