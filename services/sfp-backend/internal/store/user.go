package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
)

func (db *DB) GetUserByName(ctx context.Context, userName string) (*SysUser, error) {
	row := db.QueryRowContext(ctx, `
		SELECT user_id, dept_id, user_name, nick_name, user_type, email, phonenumber, sex,
		       avatar, password, status, del_flag, login_ip, pwd_update_date,
		       create_by, create_time, update_by, update_time, remark
		FROM sys_user
		WHERE status='0' AND del_flag='0' AND user_name=?
		ORDER BY create_time DESC LIMIT 1`, userName)
	return scanUser(row)
}

func (db *DB) GetUserBundle(ctx context.Context, userID int64) (*UserBundle, error) {
	user, err := db.getUserByID(ctx, userID)
	if err != nil {
		return nil, err
	}
	if user == nil {
		return nil, nil
	}
	bundle := &UserBundle{User: *user}
	dept, _ := db.getUserDept(ctx, userID)
	bundle.Dept = dept
	roles, _ := db.getUserRoles(ctx, userID)
	bundle.Roles = roles
	for _, r := range roles {
		if r.RoleID == 1 {
			bundle.IsAdmin = true
			break
		}
	}
	posts, _ := db.getUserPosts(ctx, userID)
	bundle.Posts = posts
	menus, _ := db.getUserMenus(ctx, userID, bundle.IsAdmin)
	bundle.Menus = menus
	return bundle, nil
}

func (db *DB) getUserByID(ctx context.Context, userID int64) (*SysUser, error) {
	row := db.QueryRowContext(ctx, `
		SELECT user_id, dept_id, user_name, nick_name, user_type, email, phonenumber, sex,
		       avatar, password, status, del_flag, login_ip, pwd_update_date,
		       create_by, create_time, update_by, update_time, remark
		FROM sys_user WHERE status='0' AND del_flag='0' AND user_id=?`, userID)
	return scanUser(row)
}

func (db *DB) getUserDept(ctx context.Context, userID int64) (*SysDept, error) {
	row := db.QueryRowContext(ctx, `
		SELECT d.dept_id, d.parent_id, d.dept_name, d.order_num, d.status
		FROM sys_user u
		JOIN sys_dept d ON u.dept_id=d.dept_id AND d.status='0' AND d.del_flag='0'
		WHERE u.user_id=?`, userID)
	var d SysDept
	if err := row.Scan(&d.DeptID, &d.ParentID, &d.DeptName, &d.OrderNum, &d.Status); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	return &d, nil
}

func (db *DB) getUserRoles(ctx context.Context, userID int64) ([]SysRole, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT DISTINCT r.role_id, r.role_name, r.role_key, r.role_sort, r.data_scope,
		       r.menu_check_strictly, r.dept_check_strictly, r.status, IFNULL(r.remark,'')
		FROM sys_user u
		LEFT JOIN sys_user_role ur ON u.user_id=ur.user_id
		LEFT JOIN sys_role r ON ur.role_id=r.role_id AND r.status='0' AND r.del_flag='0'
		WHERE u.status='0' AND u.del_flag='0' AND u.user_id=? AND r.role_id IS NOT NULL`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []SysRole
	for rows.Next() {
		var r SysRole
		var mcs, dcs int
		if err := rows.Scan(&r.RoleID, &r.RoleName, &r.RoleKey, &r.RoleSort, &r.DataScope,
			&mcs, &dcs, &r.Status, &r.Remark); err != nil {
			return nil, err
		}
		r.MenuCheckStrictly = mcs == 1
		r.DeptCheckStrictly = dcs == 1
		out = append(out, r)
	}
	return out, rows.Err()
}

func (db *DB) getUserPosts(ctx context.Context, userID int64) ([]SysPost, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT DISTINCT p.post_id, p.post_name, p.post_code
		FROM sys_user u
		LEFT JOIN sys_user_post up ON u.user_id=up.user_id
		LEFT JOIN sys_post p ON up.post_id=p.post_id AND p.status='0'
		WHERE u.user_id=? AND p.post_id IS NOT NULL`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []SysPost
	for rows.Next() {
		var p SysPost
		if err := rows.Scan(&p.PostID, &p.PostName, &p.PostCode); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (db *DB) getUserMenus(ctx context.Context, userID int64, isAdmin bool) ([]SysMenu, error) {
	var rows *sql.Rows
	var err error
	if isAdmin {
		rows, err = db.QueryContext(ctx, `
			SELECT menu_id, menu_name, parent_id, order_num, path, component, query, route_name,
			       is_frame, is_cache, menu_type, visible, status, perms, icon,
			       create_by, create_time, update_by, update_time, IFNULL(remark,'')
			FROM sys_menu WHERE status='0' ORDER BY order_num`)
	} else {
		rows, err = db.QueryContext(ctx, `
			SELECT DISTINCT m.menu_id, m.menu_name, m.parent_id, m.order_num, m.path, m.component, m.query, m.route_name,
			       m.is_frame, m.is_cache, m.menu_type, m.visible, m.status, m.perms, m.icon,
			       m.create_by, m.create_time, m.update_by, m.update_time, IFNULL(m.remark,'')
			FROM sys_user u
			LEFT JOIN sys_user_role ur ON u.user_id=ur.user_id
			LEFT JOIN sys_role r ON ur.role_id=r.role_id AND r.status='0' AND r.del_flag='0'
			LEFT JOIN sys_role_menu rm ON r.role_id=rm.role_id
			LEFT JOIN sys_menu m ON rm.menu_id=m.menu_id AND m.status='0'
			WHERE u.status='0' AND u.del_flag='0' AND u.user_id=? AND m.menu_id IS NOT NULL
			ORDER BY m.order_num`, userID)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMenus(rows)
}

func (db *DB) UpdateLoginDate(ctx context.Context, userID int64) error {
	_, err := db.ExecContext(ctx, `UPDATE sys_user SET login_date=NOW() WHERE user_id=?`, userID)
	return err
}

func scanUser(row *sql.Row) (*SysUser, error) {
	var u SysUser
	err := row.Scan(&u.UserID, &u.DeptID, &u.UserName, &u.NickName, &u.UserType, &u.Email,
		&u.Phonenumber, &u.Sex, &u.Avatar, &u.Password, &u.Status, &u.DelFlag, &u.LoginIP,
		&u.PwdUpdateDate, &u.CreateBy, &u.CreateTime, &u.UpdateBy, &u.UpdateTime, &u.Remark)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &u, nil
}

func scanMenus(rows *sql.Rows) ([]SysMenu, error) {
	var out []SysMenu
	for rows.Next() {
		var m SysMenu
		if err := rows.Scan(&m.MenuID, &m.MenuName, &m.ParentID, &m.OrderNum, &m.Path, &m.Component,
			&m.Query, &m.RouteName, &m.IsFrame, &m.IsCache, &m.MenuType, &m.Visible, &m.Status,
			&m.Perms, &m.Icon, &m.CreateBy, &m.CreateTime, &m.UpdateBy, &m.UpdateTime, &m.Remark); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

func joinIDs(ids []int64) string {
	parts := make([]string, len(ids))
	for i, id := range ids {
		parts[i] = fmt.Sprintf("%d", id)
	}
	return strings.Join(parts, ",")
}
