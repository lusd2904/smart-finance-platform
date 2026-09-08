package handlers

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/jobs"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/response"
)

type InternalJobs struct {
	Runner *jobs.Runner
	Token  string
}

func (h *InternalJobs) Run(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	token := strings.TrimSpace(h.Token)
	if token == "" {
		token = strings.TrimSpace(os.Getenv("INTERNAL_JOB_TOKEN"))
	}
	if token == "" {
		response.Error(w, "INTERNAL_JOB_TOKEN not configured")
		return
	}
	if strings.TrimSpace(r.Header.Get("X-Internal-Token")) != token {
		response.Unauthorized(w, "invalid internal token")
		return
	}
	var body struct {
		Type    string                 `json:"type"`
		Payload map[string]interface{} `json:"payload"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	jobType := strings.TrimSpace(body.Type)
	if jobType == "" {
		response.Error(w, "missing job type")
		return
	}
	result, err := h.Runner.Run(r.Context(), jobType, body.Payload)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, map[string]interface{}{"ok": true, "type": jobType, "result": result})
}
