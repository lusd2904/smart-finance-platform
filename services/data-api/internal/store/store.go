package store

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/config"
)

type DB struct {
	sql *sql.DB
}

func New(cfg *config.Config) (*DB, error) {
	db, err := sql.Open("mysql", cfg.MySQLDSN())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(12)
	db.SetMaxIdleConns(6)
	db.SetConnMaxLifetime(30 * time.Minute)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &DB{sql: db}, nil
}

func (d *DB) Close() error { return d.sql.Close() }

type Page struct {
	Rows     []map[string]interface{}
	PageNum  int
	PageSize int
	Total    int
	HasNext  bool
}

func paginate(pageNum, pageSize, total int) Page {
	if pageNum < 1 {
		pageNum = 1
	}
	if pageSize < 1 {
		pageSize = 10
	}
	hasNext := pageNum*pageSize < total
	return Page{PageNum: pageNum, PageSize: pageSize, Total: total, HasNext: hasNext}
}

func fmtTime(t sql.NullTime) interface{} {
	if t.Valid {
		return t.Time.Format("2006-01-02 15:04:05")
	}
	return nil
}

func fmtDate(t sql.NullTime) interface{} {
	if t.Valid {
		return t.Time.Format("2006-01-02")
	}
	return nil
}

func nullFloat(v sql.NullFloat64) interface{} {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func nullInt(v sql.NullInt64) interface{} {
	if v.Valid {
		return v.Int64
	}
	return nil
}

func nullStr(v sql.NullString) interface{} {
	if v.Valid {
		return v.String
	}
	return nil
}

func countQuery(ctx context.Context, db *sql.DB, query string, args ...interface{}) (int, error) {
	var total int
	err := db.QueryRowContext(ctx, query, args...).Scan(&total)
	return total, err
}

func likeArg(s string) string {
	return fmt.Sprintf("%%%s%%", s)
}
