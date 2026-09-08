package store

import (
	"database/sql"
	"fmt"

	_ "github.com/go-sql-driver/mysql"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
)

// NewMySQLOnly opens a MySQL connection for one-shot maintenance tools (no Influx/Redis).
func NewMySQLOnly(cfg config.Config) (*Service, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=true&loc=Local",
		cfg.MySQLUser, cfg.MySQLPassword, cfg.MySQLHost, cfg.MySQLPort, cfg.MySQLDatabase)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(2)
	db.SetMaxIdleConns(1)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Service{db: db, cfg: cfg}, nil
}
