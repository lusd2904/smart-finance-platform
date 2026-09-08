package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

func (s *Server) RoleList(w http.ResponseWriter, r *http.Request) {
	q := store.RoleListQuery{
		PageNum:  queryInt(r, "pageNum", 1),
		PageSize: queryInt(r, "pageSize", 10),
		RoleName: r.URL.Query().Get("roleName"),
		RoleKey:  r.URL.Query().Get("roleKey"),
		Status:   r.URL.Query().Get("status"),
	}
	rows, total, err := s.DB.ListRoles(r.Context(), q)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	hasNext := q.PageNum*q.PageSize < total
	response.Page(w, rows, q.PageNum, q.PageSize, total, hasNext)
}

func (s *Server) RoleGet(w http.ResponseWriter, r *http.Request) {
	id := pathInt64(r.URL.Path, "/system/role/", "")
	m, err := s.DB.GetRoleByID(r.Context(), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, m)
}

func (s *Server) RoleAdd(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	menuIDs := intSliceFromJSON(body["menuIds"])
	if err := s.DB.InsertRole(r.Context(), body, menuIDs, operatorName(r)); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "新增成功")
}

func (s *Server) RoleEdit(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	roleID := intField(body, "roleId")
	menuIDs := intSliceFromJSON(body["menuIds"])
	if err := s.DB.UpdateRole(r.Context(), roleID, body, menuIDs, operatorName(r), false); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "更新成功")
}

func (s *Server) RoleChangeStatus(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	roleID := intField(body, "roleId")
	if err := s.DB.UpdateRole(r.Context(), roleID, body, nil, operatorName(r), true); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "操作成功")
}

func (s *Server) RoleDataScope(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	roleID := intField(body, "roleId")
	deptIDs := intSliceFromJSON(body["deptIds"])
	if err := s.DB.UpdateRoleDataScope(r.Context(), roleID, strField(body, "dataScope"), deptIDs, operatorName(r)); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "操作成功")
}

func (s *Server) RoleDelete(w http.ResponseWriter, r *http.Request) {
	raw := strings.TrimPrefix(r.URL.Path, "/system/role/")
	ids := parseIDList(raw)
	if err := s.DB.DeleteRoles(r.Context(), ids); err != nil {
		response.Warn(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "删除成功")
}

func (s *Server) RoleDeptTree(w http.ResponseWriter, r *http.Request) {
	roleID := pathInt64(r.URL.Path, "/system/role/deptTree/", "")
	tree, err := s.DB.ListDeptTree(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	checked, _ := s.DB.GetRoleDeptIDs(r.Context(), roleID)
	response.SuccessModel(w, "操作成功", map[string]interface{}{
		"depts": tree, "checkedKeys": checked,
	})
}

func (s *Server) RoleAuthUserAllocated(w http.ResponseWriter, r *http.Request) {
	s.roleAuthUserList(w, r, true)
}

func (s *Server) RoleAuthUserUnallocated(w http.ResponseWriter, r *http.Request) {
	s.roleAuthUserList(w, r, false)
}

func (s *Server) roleAuthUserList(w http.ResponseWriter, r *http.Request, allocated bool) {
	roleID := queryInt64(r, "roleId")
	pageNum := queryInt(r, "pageNum", 1)
	pageSize := queryInt(r, "pageSize", 10)
	rows, total, err := s.DB.ListRoleUsers(r.Context(), roleID, allocated, pageNum, pageSize,
		r.URL.Query().Get("userName"), r.URL.Query().Get("phonenumber"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	hasNext := pageNum*pageSize < total
	response.Page(w, rows, pageNum, pageSize, total, hasNext)
}

func (s *Server) RoleAuthUserCancel(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	roleID := intField(body, "roleId")
	userID := intField(body, "userId")
	if err := s.DB.CancelRoleUsers(r.Context(), roleID, []int64{userID}); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateUser(r.Context(), userID)
	response.SuccessMsg(w, "操作成功")
}

func (s *Server) RoleAuthUserCancelAll(w http.ResponseWriter, r *http.Request) {
	roleID := queryInt64(r, "roleId")
	userIDs := parseIDList(r.URL.Query().Get("userIds"))
	if err := s.DB.CancelRoleUsers(r.Context(), roleID, userIDs); err != nil {
		response.Error(w, err.Error())
		return
	}
	for _, uid := range userIDs {
		s.Auth.InvalidateUser(r.Context(), uid)
	}
	response.SuccessMsg(w, "操作成功")
}

func (s *Server) RoleAuthUserSelectAll(w http.ResponseWriter, r *http.Request) {
	roleID := queryInt64(r, "roleId")
	userIDs := parseIDList(r.URL.Query().Get("userIds"))
	if err := s.DB.AssignRoleUsers(r.Context(), roleID, userIDs); err != nil {
		response.Error(w, err.Error())
		return
	}
	for _, uid := range userIDs {
		s.Auth.InvalidateUser(r.Context(), uid)
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "操作成功")
}
