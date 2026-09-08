package store

import (
	"database/sql"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
)

type DB struct {
	*sql.DB
}

func Open(cfg *config.Config) (*DB, error) {
	db, err := sql.Open("mysql", cfg.MySQLDSN())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(4)
	db.SetConnMaxLifetime(30 * time.Minute)
	if err := db.Ping(); err != nil {
		_ = db.Close()
		return nil, err
	}
	return &DB{DB: db}, nil
}

type SysUser struct {
	UserID         int64
	DeptID         sql.NullInt64
	UserName       string
	NickName       string
	UserType       string
	Email          string
	Phonenumber    string
	Sex            string
	Avatar         string
	Password       string
	Status         string
	DelFlag        string
	LoginIP        string
	PwdUpdateDate  sql.NullTime
	CreateBy       string
	CreateTime     sql.NullTime
	UpdateBy       string
	UpdateTime     sql.NullTime
	Remark         string
}

type SysDept struct {
	DeptID   int64  `json:"deptId"`
	ParentID int64  `json:"parentId"`
	DeptName string `json:"deptName"`
	OrderNum int    `json:"orderNum"`
	Status   string `json:"status"`
}

type SysRole struct {
	RoleID            int64  `json:"roleId"`
	RoleName          string `json:"roleName"`
	RoleKey           string `json:"roleKey"`
	RoleSort          int    `json:"roleSort"`
	DataScope         string `json:"dataScope"`
	MenuCheckStrictly bool   `json:"menuCheckStrictly"`
	DeptCheckStrictly bool   `json:"deptCheckStrictly"`
	Status            string `json:"status"`
	Remark            string `json:"remark"`
}

type SysMenu struct {
	MenuID     int64
	MenuName   string
	ParentID   int64
	OrderNum   int
	Path       string
	Component  sql.NullString
	Query      sql.NullString
	RouteName  sql.NullString
	IsFrame    int
	IsCache    int
	MenuType   string
	Visible    string
	Status     string
	Perms      sql.NullString
	Icon       string
	CreateBy   string
	CreateTime sql.NullTime
	UpdateBy   string
	UpdateTime sql.NullTime
	Remark     string
}

type SysPost struct {
	PostID   int64  `json:"postId"`
	PostName string `json:"postName"`
	PostCode string `json:"postCode"`
}

type UserBundle struct {
	User    SysUser
	Dept    *SysDept
	Roles   []SysRole
	Posts   []SysPost
	Menus   []SysMenu
	IsAdmin bool
}

type CurrentUserPayload struct {
	Permissions         []string               `json:"permissions"`
	Roles               []string               `json:"roles"`
	User                map[string]interface{} `json:"user"`
	IsDefaultModifyPwd  bool                   `json:"isDefaultModifyPwd"`
	IsPasswordExpired   bool                   `json:"isPasswordExpired"`
}
