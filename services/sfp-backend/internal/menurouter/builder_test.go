package menurouter_test

import (
	"database/sql"
	"encoding/json"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/menurouter"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

func TestBuildRoutersShape(t *testing.T) {
	menus := []store.SysMenu{
		{MenuID: 1, MenuName: "系统管理", ParentID: 0, OrderNum: 1, Path: "system", MenuType: "M", Visible: "0", IsFrame: 1, Component: sql.NullString{String: "", Valid: false}},
		{MenuID: 100, MenuName: "用户管理", ParentID: 1, OrderNum: 1, Path: "user", Component: sql.NullString{String: "system/user/index", Valid: true}, MenuType: "C", Visible: "0", IsFrame: 1},
	}
	routers := menurouter.BuildRouters(menus)
	if len(routers) != 1 {
		t.Fatalf("expected 1 top router, got %d", len(routers))
	}
	if routers[0].Path != "/system" {
		t.Fatalf("expected path /system, got %q", routers[0].Path)
	}
	if routers[0].Component != "Layout" {
		t.Fatalf("expected Layout component, got %q", routers[0].Component)
	}
	if len(routers[0].Children) != 1 {
		t.Fatalf("expected 1 child, got %d", len(routers[0].Children))
	}
	raw, err := json.Marshal(routers[0])
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	if _, ok := m["meta"]; !ok {
		t.Fatalf("router missing meta: %v", m)
	}
}

func TestGetRouteName(t *testing.T) {
	routers := menurouter.BuildRouters([]store.SysMenu{
		{MenuID: 1, MenuName: "Dir", ParentID: 0, Path: "system", MenuType: "M", Visible: "0", IsFrame: 1},
		{MenuID: 100, MenuName: "User", ParentID: 1, Path: "user", RouteName: sql.NullString{String: "User", Valid: true},
			Component: sql.NullString{String: "system/user/index", Valid: true}, MenuType: "C", Visible: "0", IsFrame: 1},
	})
	if len(routers) == 0 || len(routers[0].Children) == 0 {
		t.Fatal("expected nested router")
	}
	if routers[0].Children[0].Name != "User" {
		t.Fatalf("expected route name User, got %q", routers[0].Children[0].Name)
	}
}
