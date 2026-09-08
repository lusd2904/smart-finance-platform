package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

func (s *Server) MenuList(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	rows, err := s.DB.ListMenus(r.Context(), r.URL.Query().Get("menuName"), r.URL.Query().Get("status"), user.Admin, user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, rows)
}

func (s *Server) MenuGet(w http.ResponseWriter, r *http.Request) {
	id := pathInt64(r.URL.Path, "/system/menu/", "")
	m, err := s.DB.GetMenuByID(r.Context(), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, m)
}

func (s *Server) MenuTreeSelect(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	rows, err := s.DB.ListMenus(r.Context(), "", "", user.Admin, user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, storeBuildMenuTree(rows, 0))
}

func (s *Server) MenuRoleTreeSelect(w http.ResponseWriter, r *http.Request) {
	user := auth.UserFrom(r.Context())
	roleID := pathInt64(r.URL.Path, "/system/menu/roleMenuTreeselect/", "")
	rows, err := s.DB.ListMenus(r.Context(), "", "", user.Admin, user.UserID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	checked, _ := s.DB.GetRoleMenuIDs(r.Context(), roleID)
	response.SuccessModel(w, "操作成功", map[string]interface{}{
		"menus": storeBuildMenuTree(rows, 0), "checkedKeys": checked,
	})
}

func (s *Server) MenuAdd(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	if err := s.DB.InsertMenu(r.Context(), body, operatorName(r)); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "新增成功")
}

func (s *Server) MenuEdit(w http.ResponseWriter, r *http.Request) {
	var body map[string]interface{}
	if err := parseJSON(r, &body); err != nil {
		response.Error(w, "参数错误")
		return
	}
	menuID := intField(body, "menuId")
	if err := s.DB.UpdateMenu(r.Context(), menuID, body, operatorName(r)); err != nil {
		response.Error(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "更新成功")
}

func (s *Server) MenuDelete(w http.ResponseWriter, r *http.Request) {
	raw := strings.TrimPrefix(r.URL.Path, "/system/menu/")
	ids := parseIDList(raw)
	if err := s.DB.DeleteMenus(r.Context(), ids); err != nil {
		response.Warn(w, err.Error())
		return
	}
	s.Auth.InvalidateAllUsers(r.Context())
	response.SuccessMsg(w, "删除成功")
}

func storeBuildMenuTree(flat []map[string]interface{}, parentID int64) []map[string]interface{} {
	var tree []map[string]interface{}
	for _, m := range flat {
		pid := intField(m, "parentId")
		if pid == parentID {
			id := intField(m, "menuId")
			children := storeBuildMenuTree(flat, id)
			if len(children) > 0 {
				m["children"] = children
			}
			tree = append(tree, m)
		}
	}
	return tree
}
