package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

func (s *Server) AnalysisSchedulerOverview(w http.ResponseWriter, r *http.Request) {
	data, err := s.Analysis.Overview(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) AnalysisJobStatus(w http.ResponseWriter, r *http.Request) {
	jobID := pathInt64(r.URL.Path, "/analysis/scheduler/jobs/", "/status")
	if jobID <= 0 {
		response.Error(w, "任务ID不合法")
		return
	}
	var body struct {
		Status string `json:"status"`
	}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	if err := s.Analysis.ChangeStatus(r.Context(), jobID, strings.TrimSpace(body.Status)); err != nil {
		response.Warn(w, err.Error())
		return
	}
	response.SuccessMsg(w, "状态已更新，调度微服务将在数秒内同步")
}

func (s *Server) AnalysisJobRun(w http.ResponseWriter, r *http.Request) {
	jobID := pathInt64(strings.TrimSuffix(r.URL.Path, "/run"), "/analysis/scheduler/jobs/", "")
	if jobID <= 0 {
		response.Error(w, "任务ID不合法")
		return
	}
	msg, err := s.Analysis.RunOnce(r.Context(), jobID)
	if err != nil {
		response.Warn(w, err.Error())
		return
	}
	response.SuccessMsg(w, msg)
}

func (s *Server) AnalysisJobLogs(w http.ResponseWriter, r *http.Request) {
	jobID := pathInt64(strings.TrimSuffix(r.URL.Path, "/logs"), "/analysis/scheduler/jobs/", "")
	if jobID <= 0 {
		response.Error(w, "任务ID不合法")
		return
	}
	pageNum := queryInt(r, "pageNum", 1)
	pageSize := queryInt(r, "pageSize", 20)
	model, err := s.Analysis.Logs(r.Context(), jobID, pageNum, pageSize)
	if err != nil {
		response.Warn(w, err.Error())
		return
	}
	response.SuccessModel(w, "操作成功", model)
}
