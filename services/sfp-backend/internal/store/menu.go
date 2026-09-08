package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/timeutil"
)

func (db *DB) ListMenus(ctx context.Context, menuName, status string, isAdmin bool, userID int64) ([]map[string]interface{}, error) {
	where := []string{"m.status='0'"}
	args := []interface{}{}
	if menuName != "" {
		where = append(where, "m.menu_name LIKE ?")
		args = append(args, "%"+menuName+"%")
	}
	if status != "" {
		where = append(where, "m.status=?")
		args = append(args, status)
	}
	base := `
		SELECT m.menu_id, m.menu_name, m.parent_id, m.order_num, m.path, m.component, m.query, m.route_name,
		       m.is_frame, m.is_cache, m.menu_type, m.visible, m.status, m.perms, m.icon,
		       m.create_time
		FROM sys_menu m`
	if !isAdmin {
		base = `
		SELECT DISTINCT m.menu_id, m.menu_name, m.parent_id, m.order_num, m.path, m.component, m.query, m.route_name,
		       m.is_frame, m.is_cache, m.menu_type, m.visible, m.status, m.perms, m.icon,
		       m.create_time
		FROM sys_menu m
		JOIN sys_role_menu rm ON m.menu_id=rm.menu_id
		JOIN sys_user_role ur ON rm.role_id=ur.role_id AND ur.user_id=` + fmt.Sprintf("%d", userID)
	}
	rows, err := db.QueryContext(ctx, base+" WHERE "+strings.Join(where, " AND ")+" ORDER BY m.parent_id, m.order_num", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMenuMaps(rows)
}

func (db *DB) GetMenuByID(ctx context.Context, menuID int64) (map[string]interface{}, error) {
	row := db.QueryRowContext(ctx, `
		SELECT menu_id, menu_name, parent_id, order_num, path, component, query, route_name,
		       is_frame, is_cache, menu_type, visible, status, perms, icon, remark
		FROM sys_menu WHERE menu_id=?`, menuID)
	var m SysMenu
	if err := row.Scan(&m.MenuID, &m.MenuName, &m.ParentID, &m.OrderNum, &m.Path, &m.Component,
		&m.Query, &m.RouteName, &m.IsFrame, &m.IsCache, &m.MenuType, &m.Visible, &m.Status,
		&m.Perms, &m.Icon, &m.Remark); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	return menuToMap(m), nil
}

func (db *DB) ListAllMenusFlat(ctx context.Context) ([]SysMenu, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT menu_id, menu_name, parent_id, order_num, path, component, query, route_name,
		       is_frame, is_cache, menu_type, visible, status, perms, icon,
		       create_by, create_time, update_by, update_time, IFNULL(remark,'')
		FROM sys_menu WHERE status='0' ORDER BY order_num`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMenus(rows)
}

func (db *DB) GetRoleMenuIDs(ctx context.Context, roleID int64) ([]int64, error) {
	rows, err := db.QueryContext(ctx, `SELECT menu_id FROM sys_role_menu WHERE role_id=?`, roleID)
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

func (db *DB) InsertMenu(ctx context.Context, m map[string]interface{}, operator string) error {
	_, err := db.ExecContext(ctx, `
		INSERT INTO sys_menu (menu_name, parent_id, order_num, path, component, query, route_name,
		                      is_frame, is_cache, menu_type, visible, status, perms, icon,
		                      create_by, create_time, update_by, update_time, remark)
		VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW(),?,NOW(),?)`,
		m["menuName"], m["parentId"], m["orderNum"], m["path"], m["component"], m["query"], m["routeName"],
		m["isFrame"], m["isCache"], m["menuType"], m["visible"], m["status"], m["perms"], m["icon"],
		operator, operator, m["remark"])
	return err
}

func (db *DB) UpdateMenu(ctx context.Context, menuID int64, m map[string]interface{}, operator string) error {
	_, err := db.ExecContext(ctx, `
		UPDATE sys_menu SET menu_name=?, parent_id=?, order_num=?, path=?, component=?, query=?, route_name=?,
		                    is_frame=?, is_cache=?, menu_type=?, visible=?, status=?, perms=?, icon=?,
		                    remark=?, update_by=?, update_time=NOW()
		WHERE menu_id=?`,
		m["menuName"], m["parentId"], m["orderNum"], m["path"], m["component"], m["query"], m["routeName"],
		m["isFrame"], m["isCache"], m["menuType"], m["visible"], m["status"], m["perms"], m["icon"],
		m["remark"], operator, menuID)
	return err
}

func (db *DB) DeleteMenus(ctx context.Context, ids []int64) error {
	for _, id := range ids {
		var childCount int
		if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sys_menu WHERE parent_id=?`, id).Scan(&childCount); err != nil {
			return err
		}
		if childCount > 0 {
			return fmt.Errorf("存在子菜单,不允许删除")
		}
		var roleCount int
		if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sys_role_menu WHERE menu_id=?`, id).Scan(&roleCount); err != nil {
			return err
		}
		if roleCount > 0 {
			return fmt.Errorf("菜单已分配,不允许删除")
		}
		if _, err := db.ExecContext(ctx, `DELETE FROM sys_menu WHERE menu_id=?`, id); err != nil {
			return err
		}
	}
	return nil
}

func scanMenuMaps(rows *sql.Rows) ([]map[string]interface{}, error) {
	var out []map[string]interface{}
	for rows.Next() {
		var m SysMenu
		var createTime sql.NullTime
		if err := rows.Scan(&m.MenuID, &m.MenuName, &m.ParentID, &m.OrderNum, &m.Path, &m.Component,
			&m.Query, &m.RouteName, &m.IsFrame, &m.IsCache, &m.MenuType, &m.Visible, &m.Status,
			&m.Perms, &m.Icon, &createTime); err != nil {
			return nil, err
		}
		m.CreateTime = createTime
		out = append(out, menuToMap(m))
	}
	return out, rows.Err()
}

func menuToMap(m SysMenu) map[string]interface{} {
	return map[string]interface{}{
		"menuId": m.MenuID, "menuName": m.MenuName, "parentId": m.ParentID, "orderNum": m.OrderNum,
		"path": m.Path, "component": nullStr(m.Component), "query": nullStr(m.Query),
		"routeName": nullStr(m.RouteName), "isFrame": m.IsFrame, "isCache": m.IsCache,
		"menuType": m.MenuType, "visible": m.Visible, "status": m.Status,
		"perms": nullStr(m.Perms), "icon": m.Icon, "remark": m.Remark,
		"createTime": timeutil.FormatBeijing(m.CreateTime.Time),
	}
}

func nullStr(v sql.NullString) interface{} {
	if v.Valid {
		return v.String
	}
	return nil
}

func BuildMenuTree(flat []map[string]interface{}, parentID int64) []map[string]interface{} {
	var tree []map[string]interface{}
	for _, m := range flat {
		pid, _ := m["parentId"].(int64)
		if pid == parentID {
			children := BuildMenuTree(flat, m["menuId"].(int64))
			if len(children) > 0 {
				m["children"] = children
			}
			tree = append(tree, m)
		}
	}
	return tree
}
