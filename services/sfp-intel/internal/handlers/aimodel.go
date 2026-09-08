package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/store"
)

func (s *Server) AiModelList(w http.ResponseWriter, r *http.Request) {
	q := store.AiModelQuery{
		ModelCode: r.URL.Query().Get("modelCode"),
		ModelName: r.URL.Query().Get("modelName"),
		Provider:  r.URL.Query().Get("provider"),
		Status:    r.URL.Query().Get("status"),
		Scope:     r.URL.Query().Get("scope"),
		PageNum:   queryInt(r, "pageNum", 1),
		PageSize:  queryInt(r, "pageSize", 10),
	}
	rows, total, err := s.Store.ListAiModels(r.Context(), q, true)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		out = append(out, store.FormatAiModel(row, true))
	}
	response.Page(w, out, q.PageNum, q.PageSize, total)
}

func (s *Server) AiModelAll(w http.ResponseWriter, r *http.Request) {
	q := store.AiModelQuery{Status: "0"}
	rows, _, err := s.Store.ListAiModels(r.Context(), q, false)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		out = append(out, store.FormatAiModel(row, true))
	}
	response.Success(w, out)
}

func (s *Server) AiModelDetail(w http.ResponseWriter, r *http.Request) {
	idRaw := strings.TrimPrefix(r.URL.Path, "/ai/model/")
	id, err := strconv.ParseInt(strings.Trim(idRaw, "/"), 10, 64)
	if err != nil {
		response.Error(w, "invalid model id")
		return
	}
	row, err := s.Store.GetAiModel(r.Context(), id)
	if err != nil || row == nil {
		response.Error(w, "AI模型不存在")
		return
	}
	response.Success(w, store.FormatAiModel(*row, true))
}

func (s *Server) AiModelAdd(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	user := auth.UserFrom(r.Context())
	var body map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	deptID := int64(0)
	if err := s.Store.InsertAiModel(r.Context(), body, user.UserName, user.UserID, deptID); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "新增成功", nil)
}

func (s *Server) AiModelEdit(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.NotFound(w, r)
		return
	}
	user := auth.UserFrom(r.Context())
	var body map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	body["updateBy"] = user.UserName
	if err := s.Store.UpdateAiModel(r.Context(), body, user.UserName); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "修改成功", nil)
}

func (s *Server) AiModelDelete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.NotFound(w, r)
		return
	}
	idRaw := strings.TrimPrefix(r.URL.Path, "/ai/model/")
	parts := strings.Split(strings.Trim(idRaw, "/"), ",")
	ids := make([]int64, 0, len(parts))
	for _, p := range parts {
		if p == "" {
			continue
		}
		id, err := strconv.ParseInt(p, 10, 64)
		if err != nil {
			response.Error(w, "invalid model id")
			return
		}
		ids = append(ids, id)
	}
	if err := s.Store.DeleteAiModels(r.Context(), ids); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "删除成功", nil)
}
