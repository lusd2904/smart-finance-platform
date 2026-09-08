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

func (s *Server) ReqBotsGet(w http.ResponseWriter, r *http.Request) {
	bots, err := s.Store.ListReqBots(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, store.FormatReqBots(bots))
}

func (s *Server) ReqBotsPut(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.NotFound(w, r)
		return
	}
	var body struct {
		Bots []store.ReqBot `json:"bots"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	if err := s.Store.ReplaceReqBots(r.Context(), body.Bots); err != nil {
		response.Error(w, err.Error())
		return
	}
	bots, _ := s.Store.ListReqBots(r.Context())
	response.SuccessMsg(w, "机器人配置已保存，下一轮讨论生效", store.FormatReqBots(bots))
}

func (s *Server) ReqRoom(w http.ResponseWriter, r *http.Request) {
	members, err := s.Store.ListReqMembers(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	bots, err := s.Store.ListReqBots(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, store.FormatReqRoom(members, bots))
}

func (s *Server) ReqMessagesGet(w http.ResponseWriter, r *http.Request) {
	afterID := queryInt(r, "afterId", 0)
	limit := queryInt(r, "limit", 200)
	rows, err := s.Store.ListReqMessages(r.Context(), afterID, limit)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		out = append(out, store.FormatReqMessage(row))
	}
	response.Success(w, out)
}

func (s *Server) ReqMessagesPost(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	user := auth.UserFrom(r.Context())
	var body struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	content := strings.TrimSpace(body.Content)
	if content == "" {
		response.Error(w, "消息不能为空")
		return
	}
	if !s.Store.IsReqMember(user.UserName) {
		response.Error(w, "admin / niangao 不在需求沟通群中")
		return
	}
	msg, err := s.Store.AddReqMessage(r.Context(), user.UserID, user.UserName, user.UserName, "user", content)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	ticket, err := s.Queue.Submit(r.Context(), "req_send", map[string]any{
		"userId": user.UserID, "userName": user.UserName, "nickName": user.UserName,
		"userMsgId": msg.MsgID,
	})
	if err != nil {
		response.Error(w, "后台任务队列暂不可用，请稍后重试")
		return
	}
	data := map[string]interface{}{
		"accepted": ticket.Accepted, "jobId": ticket.JobID, "type": ticket.Type,
		"queue": ticket.Queue, "status": ticket.Status, "enqueuedAt": ticket.EnqueuedAt,
		"userMessage": store.FormatReqMessage(*msg),
	}
	response.SuccessMsg(w, "已发送，Grok 正在后台回复", data)
}

func (s *Server) ReqSummarize(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	user := auth.UserFrom(r.Context())
	if !s.Store.IsReqMember(user.UserName) {
		response.Error(w, "admin / niangao 不在需求沟通群中")
		return
	}
	count, err := s.Store.CountReqMessages(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	if count < 2 {
		response.Error(w, "对话太少，请先讨论需求再总结")
		return
	}
	msg, err := s.Store.AddReqMessage(r.Context(), user.UserID, user.UserName, user.UserName, "user", "请总结已确定的需求并写入需求清单。")
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	ticket, err := s.Queue.Submit(r.Context(), "req_summarize", map[string]any{
		"userId": user.UserID, "userName": user.UserName, "nickName": user.UserName,
		"userMsgId": msg.MsgID,
	})
	if err != nil {
		response.Error(w, "后台任务队列暂不可用，请稍后重试")
		return
	}
	data := map[string]interface{}{
		"accepted": ticket.Accepted, "jobId": ticket.JobID, "type": ticket.Type,
		"queue": ticket.Queue, "status": ticket.Status, "enqueuedAt": ticket.EnqueuedAt,
		"userMessage": store.FormatReqMessage(*msg),
		"message":     "已加入后台队列，确定者总结完成后会写入清单",
	}
	response.SuccessMsg(w, data["message"].(string), data)
}

func (s *Server) ReqJobStatus(w http.ResponseWriter, r *http.Request) {
	jobID := strings.TrimPrefix(r.URL.Path, "/ai/req/jobs/")
	jobID = strings.Trim(jobID, "/")
	ticket, err := s.Queue.GetTicket(r.Context(), jobID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, ticket)
}

func (s *Server) ReqItemsGet(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	items, err := s.Store.ListReqItems(r.Context(), status)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	out := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		out = append(out, store.FormatReqItem(item))
	}
	response.Success(w, out)
}

func (s *Server) ReqItemStatusPut(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.NotFound(w, r)
		return
	}
	path := strings.TrimPrefix(r.URL.Path, "/ai/req/items/")
	path = strings.TrimSuffix(path, "/status")
	id, err := strconv.ParseInt(strings.Trim(path, "/"), 10, 64)
	if err != nil {
		response.Error(w, "invalid item id")
		return
	}
	var body struct {
		Status string `json:"status"`
		Remark string `json:"remark"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	if err := s.Store.UpdateReqItemStatus(r.Context(), id, body.Status, body.Remark); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "状态已更新", nil)
}

func (s *Server) ReqItemsExport(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	data, err := store.ExportReqItems(r.Context(), s.Store, status)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}
