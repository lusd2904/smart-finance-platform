package handlers

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/internaljobs"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/opensync"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

type PlatformServer struct {
	*Server
	Sync *opensync.Service
	Jobs *internaljobs.Router
}

func (s *PlatformServer) OpenSyncToken(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	var body struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "请求体不合法")
		return
	}
	data, err := s.Sync.IssueToken(r.Context(), body.Username, body.Password)
	if err != nil {
		writeOpenSyncError(w, err)
		return
	}
	response.Success(w, data)
}

func (s *PlatformServer) OpenSyncPull(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	if _, err := s.Sync.VerifyPullToken(r.Context(), r.Header.Get("Authorization")); err != nil {
		writeOpenSyncError(w, err)
		return
	}
	var body struct {
		Datasets []string    `json:"datasets"`
		Markets  []string    `json:"markets"`
		Since    string      `json:"since"`
		Cursor   interface{} `json:"cursor"`
		Limit    *int        `json:"limit"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "请求体不合法")
		return
	}
	data, err := s.Sync.Pull(r.Context(), opensync.PullRequest{
		Datasets: body.Datasets,
		Markets:  body.Markets,
		Since:    body.Since,
		Cursor:   body.Cursor,
		Limit:    body.Limit,
	})
	if err != nil {
		writeOpenSyncError(w, err)
		return
	}
	response.Success(w, data)
}

func (s *PlatformServer) InternalJobsRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	if s.Jobs == nil || !s.Jobs.TokenConfigured() {
		http.Error(w, "INTERNAL_JOB_TOKEN not configured", http.StatusServiceUnavailable)
		return
	}
	if !s.Jobs.Authorize(r.Header.Get("X-Internal-Token")) {
		http.Error(w, "invalid internal token", http.StatusUnauthorized)
		return
	}
	var body internaljobs.Request
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	jobType := strings.TrimSpace(body.Type)
	if !s.Jobs.IsKnown(jobType) {
		http.Error(w, "unknown or non-delegatable job type: "+jobType, http.StatusBadRequest)
		return
	}
	out, err := s.Jobs.Run(r.Context(), jobType, body.Payload)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadGateway)
		return
	}
	result := out["result"]
	if result == nil {
		result = out
	}
	writeJSON(w, map[string]interface{}{"ok": true, "type": jobType, "result": result})
}

func writeOpenSyncError(w http.ResponseWriter, err error) {
	switch {
	case opensync.IsAuthError(err):
		response.Unauthorized(w, err.Error())
	case opensync.IsForbiddenError(err):
		response.Forbidden(w, err.Error())
	default:
		response.Error(w, err.Error())
	}
}

func writeJSON(w http.ResponseWriter, body interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(body)
}
