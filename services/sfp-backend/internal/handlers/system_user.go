package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

func (s *Server) UserList(w http.ResponseWriter, r *http.Request) {
	q := store.UserListQuery{
		PageNum:     queryInt(r, "pageNum", 1),
		PageSize:    queryInt(r, "pageSize", 10),
		UserName:    r.URL.Query().Get("userName"),
		Phonenumber: r.URL.Query().Get("phonenumber"),
		Status:      r.URL.Query().Get("status"),
		DeptID:      queryInt64(r, "deptId"),
	}
	rows, total, err := s.DB.ListUsers(r.Context(), q)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	hasNext := q.PageNum*q.PageSize < total
	response.Page(w, rows, q.PageNum, q.PageSize, total, hasNext)
}

func (s *Server) UserGet(w http.ResponseWriter, r *http.Request) {
	id := pathInt64(r.URL.Path, "/system/user/", "")
	if id <= 0 {
		response.Success(w, map[string]interface{}{})
		return
	}
	user, postIDs, posts, roleIDs, roles, err := s.DB.GetUserDetail(r.Context(), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessModel(w, "操作成功", map[string]interface{}{
		"data": user, "postIds": postIDs, "posts": posts, "roleIds": roleIDs, "roles": roles,
	})
}

func (s *Server) UserAdd(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	userName := strField(body, "userName")
	if exists, _ := s.DB.UserNameExists(r.Context(), userName, 0); exists {
		response.Warn(w, "新增用户"+userName+"失败，登录账号已存在")
		return
	}
	hash, err := auth.HashPassword(strField(body, "password"))
	if err != nil {
		response.Error(w, "密码加密失败")
		return
	}
	op := operatorName(r)
	roleIDs := intSliceFromJSON(body["roleIds"])
	postIDs := intSliceFromJSON(body["postIds"])
	if _, err := s.DB.InsertUser(r.Context(), body, roleIDs, postIDs, hash, op); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "新增成功")
}

func (s *Server) UserEdit(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	userID := intField(body, "userId")
	if userID == 1 {
		response.Warn(w, "不允许操作超级管理员用户")
		return
	}
	op := operatorName(r)
	roleIDs := intSliceFromJSON(body["roleIds"])
	postIDs := intSliceFromJSON(body["postIds"])
	if err := s.DB.UpdateUser(r.Context(), userID, body, roleIDs, postIDs, op); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateUser(r.Context(), userID)
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "更新成功")
}

func (s *Server) UserDelete(w http.ResponseWriter, r *http.Request) {
	raw := strings.TrimPrefix(r.URL.Path, "/system/user/")
	ids := parseIDList(raw)
	for _, id := range ids {
		if id == 1 {
			response.Warn(w, "不允许操作超级管理员用户")
			return
		}
	}
	if err := s.DB.DeleteUsers(r.Context(), ids); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "删除成功")
}

func (s *Server) UserResetPwd(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	userID := intField(body, "userId")
	hash, err := auth.HashPassword(strField(body, "password"))
	if err != nil {
		response.Error(w, "密码加密失败")
		return
	}
	if err := s.DB.ResetUserPassword(r.Context(), userID, hash, operatorName(r)); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateUser(r.Context(), userID)
	response.SuccessMsg(w, "重置成功")
}

func (s *Server) UserChangeStatus(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	userID := intField(body, "userId")
	if err := s.DB.ChangeUserStatus(r.Context(), userID, strField(body, "status"), operatorName(r)); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "操作成功")
}

func (s *Server) UserDeptTree(w http.ResponseWriter, r *http.Request) {
	tree, err := s.DB.ListDeptTree(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, tree)
}

func (s *Server) UserAuthRoleGet(w http.ResponseWriter, r *http.Request) {
	userID := pathInt64(r.URL.Path, "/system/user/authRole/", "")
	user, _, _, roleIDs, _, err := s.DB.GetUserDetail(r.Context(), userID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	roles, err := s.DB.ListAllRoles(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessModel(w, "操作成功", map[string]interface{}{
		"user": user, "roles": roles, "roleIds": roleIDs,
	})
}

func (s *Server) UserAuthRolePut(w http.ResponseWriter, r *http.Request) {
	userID := queryInt64(r, "userId")
	roleIDs := parseIDList(r.URL.Query().Get("roleIds"))
	if err := s.DB.UpdateUserRoles(r.Context(), userID, roleIDs); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateUser(r.Context(), userID)
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "授权成功")
}

func operatorName(r *http.Request) string {
	if u := auth.UserFrom(r.Context()); u != nil {
		return u.UserName
	}
	return "system"
}
