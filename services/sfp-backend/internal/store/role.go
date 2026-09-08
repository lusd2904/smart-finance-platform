package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/timeutil"
)

type RoleListQuery struct {
	PageNum  int
	PageSize int
	RoleName string
	RoleKey  string
	Status   string
}

func (db *DB) ListRoles(ctx context.Context, q RoleListQuery) ([]map[string]interface{}, int, error) {
	where := []string{"del_flag='0'"}
	args := []interface{}{}
	if q.RoleName != "" {
		where = append(where, "role_name LIKE ?")
		args = append(args, "%"+q.RoleName+"%")
	}
	if q.RoleKey != "" {
		where = append(where, "role_key LIKE ?")
		args = append(args, "%"+q.RoleKey+"%")
	}
	if q.Status != "" {
		where = append(where, "status=?")
		args = append(args, q.Status)
	}
	w := strings.Join(where, " AND ")

	var total int
	if err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sys_role WHERE "+w, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	pageNum, pageSize := q.PageNum, q.PageSize
	if pageNum <= 0 {
		pageNum = 1
	}
	if pageSize <= 0 {
		pageSize = 10
	}
	offset := (pageNum - 1) * pageSize
	queryArgs := append(args, pageSize, offset)
	rows, err := db.QueryContext(ctx, `
		SELECT role_id, role_name, role_key, role_sort, data_scope, menu_check_strictly,
		       dept_check_strictly, status, create_time, remark
		FROM sys_role WHERE `+w+` ORDER BY role_sort LIMIT ? OFFSET ?`, queryArgs...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var out []map[string]interface{}
	for rows.Next() {
		var r SysRole
		var mcs, dcs int
		var createTime sql.NullTime
		if err := rows.Scan(&r.RoleID, &r.RoleName, &r.RoleKey, &r.RoleSort, &r.DataScope,
			&mcs, &dcs, &r.Status, &createTime, &r.Remark); err != nil {
			return nil, 0, err
		}
		r.MenuCheckStrictly = mcs == 1
		r.DeptCheckStrictly = dcs == 1
		m := roleToMap(r)
		m["dataScope"] = r.DataScope
		m["menuCheckStrictly"] = r.MenuCheckStrictly
		m["deptCheckStrictly"] = r.DeptCheckStrictly
		m["createTime"] = timeutil.FormatBeijing(createTime.Time)
		out = append(out, m)
	}
	return out, total, rows.Err()
}

func (db *DB) GetRoleByID(ctx context.Context, roleID int64) (map[string]interface{}, error) {
	row := db.QueryRowContext(ctx, `
		SELECT role_id, role_name, role_key, role_sort, data_scope, menu_check_strictly,
		       dept_check_strictly, status, remark
		FROM sys_role WHERE role_id=? AND del_flag='0'`, roleID)
	var r SysRole
	var mcs, dcs int
	if err := row.Scan(&r.RoleID, &r.RoleName, &r.RoleKey, &r.RoleSort, &r.DataScope,
		&mcs, &dcs, &r.Status, &r.Remark); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	r.MenuCheckStrictly = mcs == 1
	r.DeptCheckStrictly = dcs == 1
	m := roleToMap(r)
	m["dataScope"] = r.DataScope
	m["menuCheckStrictly"] = r.MenuCheckStrictly
	m["deptCheckStrictly"] = r.DeptCheckStrictly
	return m, nil
}

func (db *DB) InsertRole(ctx context.Context, r map[string]interface{}, menuIDs []int64, operator string) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	res, err := tx.ExecContext(ctx, `
		INSERT INTO sys_role (role_name, role_key, role_sort, data_scope, menu_check_strictly, dept_check_strictly,
		                      status, del_flag, create_by, create_time, update_by, update_time, remark)
		VALUES (?,?,?,?,?,?,?,'0',?,NOW(),?,NOW(),?)`,
		r["roleName"], r["roleKey"], r["roleSort"], r["dataScope"], boolInt(r["menuCheckStrictly"]),
		boolInt(r["deptCheckStrictly"]), r["status"], operator, operator, r["remark"])
	if err != nil {
		return err
	}
	roleID, _ := res.LastInsertId()
	for _, mid := range menuIDs {
		if _, err = tx.ExecContext(ctx, `INSERT INTO sys_role_menu (role_id, menu_id) VALUES (?,?)`, roleID, mid); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (db *DB) UpdateRole(ctx context.Context, roleID int64, r map[string]interface{}, menuIDs []int64, operator string, statusOnly bool) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	if statusOnly {
		_, err = tx.ExecContext(ctx, `UPDATE sys_role SET status=?, update_by=?, update_time=NOW() WHERE role_id=?`,
			r["status"], operator, roleID)
	} else {
		_, err = tx.ExecContext(ctx, `
			UPDATE sys_role SET role_name=?, role_key=?, role_sort=?, data_scope=?,
			                    menu_check_strictly=?, dept_check_strictly=?, status=?, remark=?,
			                    update_by=?, update_time=NOW()
			WHERE role_id=?`,
			r["roleName"], r["roleKey"], r["roleSort"], r["dataScope"],
			boolInt(r["menuCheckStrictly"]), boolInt(r["deptCheckStrictly"]),
			r["status"], r["remark"], operator, roleID)
		if err != nil {
			return err
		}
		if _, err = tx.ExecContext(ctx, `DELETE FROM sys_role_menu WHERE role_id=?`, roleID); err != nil {
			return err
		}
		for _, mid := range menuIDs {
			if _, err = tx.ExecContext(ctx, `INSERT INTO sys_role_menu (role_id, menu_id) VALUES (?,?)`, roleID, mid); err != nil {
				return err
			}
		}
	}
	if err != nil {
		return err
	}
	return tx.Commit()
}

func (db *DB) UpdateRoleDataScope(ctx context.Context, roleID int64, dataScope string, deptIDs []int64, operator string) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	if _, err = tx.ExecContext(ctx, `UPDATE sys_role SET data_scope=?, update_by=?, update_time=NOW() WHERE role_id=?`,
		dataScope, operator, roleID); err != nil {
		return err
	}
	if _, err = tx.ExecContext(ctx, `DELETE FROM sys_role_dept WHERE role_id=?`, roleID); err != nil {
		return err
	}
	for _, did := range deptIDs {
		if _, err = tx.ExecContext(ctx, `INSERT INTO sys_role_dept (role_id, dept_id) VALUES (?,?)`, roleID, did); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (db *DB) DeleteRoles(ctx context.Context, ids []int64) error {
	for _, id := range ids {
		if id == 1 {
			return fmt.Errorf("不允许操作超级管理员角色")
		}
	}
	placeholders := strings.Repeat("?,", len(ids))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]interface{}, len(ids))
	for i, id := range ids {
		args[i] = id
	}
	_, err := db.ExecContext(ctx, `UPDATE sys_role SET del_flag='2' WHERE role_id IN (`+placeholders+`)`, args...)
	return err
}

func (db *DB) GetRoleDeptIDs(ctx context.Context, roleID int64) ([]int64, error) {
	rows, err := db.QueryContext(ctx, `SELECT dept_id FROM sys_role_dept WHERE role_id=?`, roleID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

func (db *DB) ListRoleUsers(ctx context.Context, roleID int64, allocated bool, pageNum, pageSize int, userName, phone string) ([]map[string]interface{}, int, error) {
	where := []string{"u.del_flag='0'"}
	args := []interface{}{roleID}
	join := `JOIN sys_user_role ur ON u.user_id=ur.user_id AND ur.role_id=?`
	if !allocated {
		join = `LEFT JOIN sys_user_role ur ON u.user_id=ur.user_id AND ur.role_id=?`
		where = append(where, "ur.user_id IS NULL")
	}
	if userName != "" {
		where = append(where, "u.user_name LIKE ?")
		args = append(args, "%"+userName+"%")
	}
	if phone != "" {
		where = append(where, "u.phonenumber LIKE ?")
		args = append(args, "%"+phone+"%")
	}
	w := strings.Join(where, " AND ")
	var total int
	countSQL := fmt.Sprintf("SELECT COUNT(*) FROM sys_user u %s WHERE %s", join, w)
	if err := db.QueryRowContext(ctx, countSQL, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	if pageNum <= 0 {
		pageNum = 1
	}
	if pageSize <= 0 {
		pageSize = 10
	}
	offset := (pageNum - 1) * pageSize
	queryArgs := append(args, pageSize, offset)
	rows, err := db.QueryContext(ctx, fmt.Sprintf(`
		SELECT u.user_id, u.user_name, u.nick_name, u.email, u.phonenumber, u.status, u.create_time
		FROM sys_user u %s WHERE %s ORDER BY u.user_id LIMIT ? OFFSET ?`, join, w), queryArgs...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	var out []map[string]interface{}
	for rows.Next() {
		var userID int64
		var userName, nickName, email, phoneNum, status string
		var createTime sql.NullTime
		if err := rows.Scan(&userID, &userName, &nickName, &email, &phoneNum, &status, &createTime); err != nil {
			return nil, 0, err
		}
		out = append(out, map[string]interface{}{
			"userId": userID, "userName": userName, "nickName": nickName,
			"email": email, "phonenumber": phoneNum, "status": status,
			"createTime": timeutil.FormatBeijing(createTime.Time),
		})
	}
	return out, total, rows.Err()
}

func (db *DB) CancelRoleUsers(ctx context.Context, roleID int64, userIDs []int64) error {
	for _, uid := range userIDs {
		if _, err := db.ExecContext(ctx, `DELETE FROM sys_user_role WHERE role_id=? AND user_id=?`, roleID, uid); err != nil {
			return err
		}
	}
	return nil
}

func (db *DB) AssignRoleUsers(ctx context.Context, roleID int64, userIDs []int64) error {
	for _, uid := range userIDs {
		var count int
		if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sys_user_role WHERE role_id=? AND user_id=?`, roleID, uid).Scan(&count); err != nil {
			return err
		}
		if count == 0 {
			if _, err := db.ExecContext(ctx, `INSERT INTO sys_user_role (role_id, user_id) VALUES (?,?)`, roleID, uid); err != nil {
				return err
			}
		}
	}
	return nil
}

func boolInt(v interface{}) int {
	switch t := v.(type) {
	case bool:
		if t {
			return 1
		}
	case float64:
		if t != 0 {
			return 1
		}
	}
	return 0
}
