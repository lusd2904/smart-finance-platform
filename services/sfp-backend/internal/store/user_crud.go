package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/timeutil"
)

type UserListQuery struct {
	PageNum      int
	PageSize     int
	UserName     string
	Phonenumber  string
	Status       string
	DeptID       int64
}

func (db *DB) ListUsers(ctx context.Context, q UserListQuery) ([]map[string]interface{}, int, error) {
	where := []string{"u.del_flag='0'"}
	args := []interface{}{}
	if q.UserName != "" {
		where = append(where, "u.user_name LIKE ?")
		args = append(args, "%"+q.UserName+"%")
	}
	if q.Phonenumber != "" {
		where = append(where, "u.phonenumber LIKE ?")
		args = append(args, "%"+q.Phonenumber+"%")
	}
	if q.Status != "" {
		where = append(where, "u.status=?")
		args = append(args, q.Status)
	}
	if q.DeptID > 0 {
		where = append(where, "(u.dept_id=? OR u.dept_id IN (SELECT dept_id FROM sys_dept WHERE FIND_IN_SET(?, ancestors)))")
		args = append(args, q.DeptID, fmt.Sprintf("%d", q.DeptID))
	}
	w := strings.Join(where, " AND ")

	var total int
	if err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM sys_user u WHERE "+w, args...).Scan(&total); err != nil {
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
		SELECT u.user_id, u.dept_id, u.user_name, u.nick_name, u.email, u.phonenumber, u.sex,
		       u.avatar, u.status, u.create_time,
		       d.dept_id, d.dept_name
		FROM sys_user u
		LEFT JOIN sys_dept d ON u.dept_id=d.dept_id
		WHERE `+w+` ORDER BY u.user_id LIMIT ? OFFSET ?`, queryArgs...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var out []map[string]interface{}
	for rows.Next() {
		var userID int64
		var deptID sql.NullInt64
		var userName, nickName, email, phone, sex, avatar, status string
		var createTime sql.NullTime
		var dDeptID sql.NullInt64
		var deptName sql.NullString
		if err := rows.Scan(&userID, &deptID, &userName, &nickName, &email, &phone, &sex,
			&avatar, &status, &createTime, &dDeptID, &deptName); err != nil {
			return nil, 0, err
		}
		row := map[string]interface{}{
			"userId": userID, "userName": userName, "nickName": nickName,
			"email": email, "phonenumber": phone, "sex": sex, "avatar": avatar, "status": status,
			"createTime": timeutil.FormatBeijing(createTime.Time),
		}
		if dDeptID.Valid {
			row["dept"] = map[string]interface{}{"deptId": dDeptID.Int64, "deptName": deptName.String}
		}
		out = append(out, row)
	}
	return out, total, rows.Err()
}

func (db *DB) GetUserDetail(ctx context.Context, userID int64) (map[string]interface{}, []int64, []map[string]interface{}, []int64, []map[string]interface{}, error) {
	bundle, err := db.GetUserBundle(ctx, userID)
	if err != nil || bundle == nil {
		return nil, nil, nil, nil, nil, err
	}
	userMap := userToMap(bundle.User, bundle.Dept, bundle.Roles, bundle.Posts)
	roleIDs := make([]int64, len(bundle.Roles))
	roles := make([]map[string]interface{}, len(bundle.Roles))
	for i, r := range bundle.Roles {
		roleIDs[i] = r.RoleID
		roles[i] = roleToMap(r)
	}
	postIDs := make([]int64, len(bundle.Posts))
	posts := make([]map[string]interface{}, len(bundle.Posts))
	for i, p := range bundle.Posts {
		postIDs[i] = p.PostID
		posts[i] = map[string]interface{}{"postId": p.PostID, "postName": p.PostName, "postCode": p.PostCode}
	}
	return userMap, postIDs, posts, roleIDs, roles, nil
}

func (db *DB) InsertUser(ctx context.Context, u map[string]interface{}, roleIDs, postIDs []int64, passwordHash, operator string) (int64, error) {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback() }()

	res, err := tx.ExecContext(ctx, `
		INSERT INTO sys_user (dept_id, user_name, nick_name, email, phonenumber, sex, password, status,
		                      create_by, create_time, update_by, update_time, remark, del_flag, pwd_update_date)
		VALUES (?,?,?,?,?,?,?,?,?,NOW(),?,?,?,'0',NOW())`,
		u["deptId"], u["userName"], u["nickName"], u["email"], u["phonenumber"], u["sex"],
		passwordHash, u["status"], operator, operator, time.Now(), u["remark"])
	if err != nil {
		return 0, err
	}
	userID, _ := res.LastInsertId()
	for _, rid := range roleIDs {
		if _, err := tx.ExecContext(ctx, `INSERT INTO sys_user_role (user_id, role_id) VALUES (?,?)`, userID, rid); err != nil {
			return 0, err
		}
	}
	for _, pid := range postIDs {
		if _, err := tx.ExecContext(ctx, `INSERT INTO sys_user_post (user_id, post_id) VALUES (?,?)`, userID, pid); err != nil {
			return 0, err
		}
	}
	return userID, tx.Commit()
}

func (db *DB) UpdateUser(ctx context.Context, userID int64, u map[string]interface{}, roleIDs, postIDs []int64, operator string) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()

	_, err = tx.ExecContext(ctx, `
		UPDATE sys_user SET dept_id=?, nick_name=?, email=?, phonenumber=?, sex=?, status=?,
		                    remark=?, update_by=?, update_time=NOW()
		WHERE user_id=? AND del_flag='0'`,
		u["deptId"], u["nickName"], u["email"], u["phonenumber"], u["sex"], u["status"],
		u["remark"], operator, userID)
	if err != nil {
		return err
	}
	if _, err = tx.ExecContext(ctx, `DELETE FROM sys_user_role WHERE user_id=?`, userID); err != nil {
		return err
	}
	for _, rid := range roleIDs {
		if _, err = tx.ExecContext(ctx, `INSERT INTO sys_user_role (user_id, role_id) VALUES (?,?)`, userID, rid); err != nil {
			return err
		}
	}
	if _, err = tx.ExecContext(ctx, `DELETE FROM sys_user_post WHERE user_id=?`, userID); err != nil {
		return err
	}
	for _, pid := range postIDs {
		if _, err = tx.ExecContext(ctx, `INSERT INTO sys_user_post (user_id, post_id) VALUES (?,?)`, userID, pid); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (db *DB) DeleteUsers(ctx context.Context, ids []int64) error {
	if len(ids) == 0 {
		return nil
	}
	placeholders := strings.Repeat("?,", len(ids))
	placeholders = placeholders[:len(placeholders)-1]
	args := make([]interface{}, len(ids))
	for i, id := range ids {
		args[i] = id
	}
	_, err := db.ExecContext(ctx, `UPDATE sys_user SET del_flag='2' WHERE user_id IN (`+placeholders+`)`, args...)
	return err
}

func (db *DB) ResetUserPassword(ctx context.Context, userID int64, hash, operator string) error {
	_, err := db.ExecContext(ctx, `
		UPDATE sys_user SET password=?, pwd_update_date=NOW(), update_by=?, update_time=NOW()
		WHERE user_id=?`, hash, operator, userID)
	return err
}

func (db *DB) ChangeUserStatus(ctx context.Context, userID int64, status, operator string) error {
	_, err := db.ExecContext(ctx, `
		UPDATE sys_user SET status=?, update_by=?, update_time=NOW() WHERE user_id=?`, status, operator, userID)
	return err
}

func (db *DB) UpdateUserRoles(ctx context.Context, userID int64, roleIDs []int64) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	if _, err = tx.ExecContext(ctx, `DELETE FROM sys_user_role WHERE user_id=?`, userID); err != nil {
		return err
	}
	for _, rid := range roleIDs {
		if _, err = tx.ExecContext(ctx, `INSERT INTO sys_user_role (user_id, role_id) VALUES (?,?)`, userID, rid); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (db *DB) ListAllRoles(ctx context.Context) ([]map[string]interface{}, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT role_id, role_name, role_key, role_sort, status, remark
		FROM sys_role WHERE del_flag='0' ORDER BY role_sort`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []map[string]interface{}
	for rows.Next() {
		var r SysRole
		if err := rows.Scan(&r.RoleID, &r.RoleName, &r.RoleKey, &r.RoleSort, &r.Status, &r.Remark); err != nil {
			return nil, err
		}
		out = append(out, roleToMap(r))
	}
	return out, rows.Err()
}

func userToMap(u SysUser, dept *SysDept, roles []SysRole, posts []SysPost) map[string]interface{} {
	m := map[string]interface{}{
		"userId": u.UserID, "userName": u.UserName, "nickName": u.NickName,
		"email": u.Email, "phonenumber": u.Phonenumber, "sex": u.Sex, "avatar": u.Avatar,
		"status": u.Status, "remark": u.Remark,
	}
	if u.DeptID.Valid {
		m["deptId"] = u.DeptID.Int64
	}
	if dept != nil {
		m["dept"] = map[string]interface{}{"deptId": dept.DeptID, "deptName": dept.DeptName}
	}
	roleList := make([]map[string]interface{}, len(roles))
	for i, r := range roles {
		roleList[i] = roleToMap(r)
	}
	m["role"] = roleList
	return m
}

func roleToMap(r SysRole) map[string]interface{} {
	return map[string]interface{}{
		"roleId": r.RoleID, "roleName": r.RoleName, "roleKey": r.RoleKey,
		"roleSort": r.RoleSort, "status": r.Status, "remark": r.Remark,
	}
}

func (db *DB) UserNameExists(ctx context.Context, userName string, excludeID int64) (bool, error) {
	var id int64
	err := db.QueryRowContext(ctx, `SELECT user_id FROM sys_user WHERE del_flag='0' AND user_name=? LIMIT 1`, userName).Scan(&id)
	if err == sql.ErrNoRows {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return id != excludeID, nil
}
