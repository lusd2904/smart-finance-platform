package menurouter

import (
	"database/sql"
	"sort"
	"strings"
	"unicode"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

const (
	typeDir      = "M"
	typeMenu     = "C"
	layout       = "Layout"
	innerLink    = "InnerLink"
	parentView   = "ParentView"
	noFrame      = 1
)

type Meta struct {
	Title   string  `json:"title"`
	Icon    string  `json:"icon"`
	NoCache bool    `json:"noCache"`
	Link    *string `json:"link"`
}

type Router struct {
	Name       string   `json:"name,omitempty"`
	Path       string   `json:"path,omitempty"`
	Hidden     bool     `json:"hidden,omitempty"`
	Redirect   string   `json:"redirect,omitempty"`
	Component  string   `json:"component,omitempty"`
	AlwaysShow *bool    `json:"alwaysShow,omitempty"`
	Query      *string  `json:"query,omitempty"`
	Meta       *Meta    `json:"meta,omitempty"`
	Children   []Router `json:"children,omitempty"`
}

type menuNode struct {
	menu     store.SysMenu
	children []*menuNode
}

func BuildRouters(menus []store.SysMenu) []Router {
	filtered := make([]store.SysMenu, 0, len(menus))
	for _, m := range menus {
		if m.MenuType == typeDir || m.MenuType == typeMenu {
			filtered = append(filtered, m)
		}
	}
	sort.Slice(filtered, func(i, j int) bool { return filtered[i].OrderNum < filtered[j].OrderNum })
	tree := buildMenuTree(0, filtered)
	return generateUserRouterMenu(tree)
}

func buildMenuTree(pid int64, list []store.SysMenu) []*menuNode {
	var nodes []*menuNode
	for _, m := range list {
		if m.ParentID == pid {
			n := &menuNode{menu: m, children: buildMenuTree(m.MenuID, list)}
			nodes = append(nodes, n)
		}
	}
	return nodes
}

func generateUserRouterMenu(nodes []*menuNode) []Router {
	var routers []Router
	for _, n := range nodes {
		m := n.menu
		r := Router{
			Hidden:    m.Visible == "1",
			Name:      getRouterName(m),
			Path:      getRouterPath(m),
			Component: getComponent(m),
		}
		if m.Query.Valid {
			q := m.Query.String
			r.Query = &q
		}
		link := linkFor(m.Path)
		r.Meta = &Meta{Title: m.MenuName, Icon: m.Icon, NoCache: m.IsCache == 1, Link: link}

		if len(n.children) > 0 && m.MenuType == typeDir {
			t := true
			r.AlwaysShow = &t
			r.Redirect = "noRedirect"
			r.Children = generateUserRouterMenu(n.children)
		} else if isMenuFrame(m) {
			r.Meta = nil
			child := Router{
				Path: m.Path, Component: nullStr(m.Component),
				Name: getRouteName(m.RouteName, m.Path),
				Meta: &Meta{Title: m.MenuName, Icon: m.Icon, NoCache: m.IsCache == 1, Link: link},
			}
			if m.Query.Valid {
				q := m.Query.String
				child.Query = &q
			}
			r.Children = []Router{child}
		} else if m.ParentID == 0 && isInnerLink(m) {
			r.Meta = &Meta{Title: m.MenuName, Icon: m.Icon}
			r.Path = "/"
			rp := innerLinkReplaceEach(m.Path)
			r.Children = []Router{{
				Path: rp, Component: innerLink,
				Name: getRouteName(m.RouteName, m.Path),
				Meta: &Meta{Title: m.MenuName, Icon: m.Icon, Link: linkFor(m.Path)},
			}}
		}
		routers = append(routers, r)
	}
	return routers
}

func getRouterName(m store.SysMenu) string {
	if isMenuFrame(m) {
		return ""
	}
	return getRouteName(m.RouteName, m.Path)
}

func getRouteName(name sql.NullString, path string) string {
	if name.Valid && name.String != "" {
		return capitalize(name.String)
	}
	return capitalize(path)
}

func capitalize(s string) string {
	if s == "" {
		return ""
	}
	runes := []rune(s)
	runes[0] = unicode.ToUpper(runes[0])
	return string(runes)
}

func getRouterPath(m store.SysMenu) string {
	path := m.Path
	if m.ParentID != 0 && isInnerLink(m) {
		path = innerLinkReplaceEach(path)
	}
	if m.ParentID == 0 && m.MenuType == typeDir && m.IsFrame == noFrame {
		path = "/" + m.Path
	} else if isMenuFrame(m) {
		path = "/"
	}
	return path
}

func getComponent(m store.SysMenu) string {
	component := layout
	if m.Component.Valid && m.Component.String != "" && !isMenuFrame(m) {
		component = m.Component.String
	} else if (!m.Component.Valid || m.Component.String == "") && m.ParentID != 0 && isInnerLink(m) {
		component = innerLink
	} else if (!m.Component.Valid || m.Component.String == "") && isParentView(m) {
		component = parentView
	}
	return component
}

func isMenuFrame(m store.SysMenu) bool {
	return m.ParentID == 0 && m.MenuType == typeMenu && m.IsFrame == noFrame
}

func isInnerLink(m store.SysMenu) bool {
	return m.IsFrame == noFrame && isHTTP(m.Path)
}

func isParentView(m store.SysMenu) bool {
	return m.ParentID != 0 && m.MenuType == typeDir
}

func isHTTP(link string) bool {
	return strings.HasPrefix(link, "http://") || strings.HasPrefix(link, "https://")
}

func linkFor(path string) *string {
	if isHTTP(path) {
		return &path
	}
	return nil
}

func innerLinkReplaceEach(path string) string {
	repl := []struct{ old, new string }{
		{"http://", ""}, {"https://", ""}, {"www.", ""}, {".", "/"}, {":", "/"},
	}
	for _, r := range repl {
		path = strings.ReplaceAll(path, r.old, r.new)
	}
	return path
}

func nullStr(v sql.NullString) string {
	if v.Valid {
		return v.String
	}
	return ""
}
