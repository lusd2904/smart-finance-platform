package store

import (
	"context"
)

func (db *DB) ListDeptTree(ctx context.Context) ([]map[string]interface{}, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT dept_id, parent_id, dept_name, order_num, status
		FROM sys_dept WHERE del_flag='0' AND status='0' ORDER BY parent_id, order_num`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var flat []map[string]interface{}
	for rows.Next() {
		var d SysDept
		if err := rows.Scan(&d.DeptID, &d.ParentID, &d.DeptName, &d.OrderNum, &d.Status); err != nil {
			return nil, err
		}
		flat = append(flat, map[string]interface{}{
			"id": d.DeptID, "label": d.DeptName, "parentId": d.ParentID,
		})
	}
	return buildDeptTree(flat, 0), rows.Err()
}

func buildDeptTree(flat []map[string]interface{}, parentID int64) []map[string]interface{} {
	var tree []map[string]interface{}
	for _, d := range flat {
		pid, _ := d["parentId"].(int64)
		if pid == parentID {
			id, _ := d["id"].(int64)
			children := buildDeptTree(flat, id)
			node := map[string]interface{}{"id": d["id"], "label": d["label"]}
			if len(children) > 0 {
				node["children"] = children
			}
			tree = append(tree, node)
		}
	}
	return tree
}
