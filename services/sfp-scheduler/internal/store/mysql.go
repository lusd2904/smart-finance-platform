package store

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

type JobRow struct {
	JobID          int64
	JobName        string
	JobGroup       string
	JobExecutor    string
	InvokeTarget   string
	JobArgs        string
	JobKwargs      string
	CronExpression string
	MisfirePolicy  string
	Concurrent     string
	Status         string
	UpdateTime     time.Time
}

type Store struct {
	db *sql.DB
}

func Open(dsn string) (*Store, error) {
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(2)
	db.SetConnMaxLifetime(30 * time.Minute)
	if err := db.Ping(); err != nil {
		_ = db.Close()
		return nil, err
	}
	return &Store{db: db}, nil
}

func DSN(host string, port int, user, password, database string) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true&loc=Local&charset=utf8mb4",
		user, password, host, port, database)
}

func (s *Store) Close() error {
	if s == nil || s.db == nil {
		return nil
	}
	return s.db.Close()
}

func (s *Store) Ping(ctx context.Context) error {
	return s.db.PingContext(ctx)
}

func (s *Store) ListJobs(ctx context.Context) ([]JobRow, error) {
	const q = `
SELECT job_id, job_name, IFNULL(job_group,''), IFNULL(job_executor,'default'),
       invoke_target, IFNULL(job_args,''), IFNULL(job_kwargs,''),
       IFNULL(cron_expression,''), IFNULL(misfire_policy,'3'),
       IFNULL(concurrent,'1'), IFNULL(status,'1'), IFNULL(update_time, create_time)
FROM sys_job`
	rows, err := s.db.QueryContext(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []JobRow
	for rows.Next() {
		var row JobRow
		var update sql.NullTime
		if err := rows.Scan(
			&row.JobID, &row.JobName, &row.JobGroup, &row.JobExecutor,
			&row.InvokeTarget, &row.JobArgs, &row.JobKwargs,
			&row.CronExpression, &row.MisfirePolicy, &row.Concurrent,
			&row.Status, &update,
		); err != nil {
			return nil, err
		}
		if update.Valid {
			row.UpdateTime = update.Time
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func (s *Store) GetJob(ctx context.Context, jobID int64) (*JobRow, error) {
	const q = `
SELECT job_id, job_name, IFNULL(job_group,''), IFNULL(job_executor,'default'),
       invoke_target, IFNULL(job_args,''), IFNULL(job_kwargs,''),
       IFNULL(cron_expression,''), IFNULL(misfire_policy,'3'),
       IFNULL(concurrent,'1'), IFNULL(status,'1'), IFNULL(update_time, create_time)
FROM sys_job WHERE job_id = ?`
	row := s.db.QueryRowContext(ctx, q, jobID)
	var out JobRow
	var update sql.NullTime
	if err := row.Scan(
		&out.JobID, &out.JobName, &out.JobGroup, &out.JobExecutor,
		&out.InvokeTarget, &out.JobArgs, &out.JobKwargs,
		&out.CronExpression, &out.MisfirePolicy, &out.Concurrent,
		&out.Status, &update,
	); err != nil {
		return nil, err
	}
	if update.Valid {
		out.UpdateTime = update.Time
	}
	return &out, nil
}

func (s *Store) InsertJobLog(ctx context.Context, row JobRow, trigger, message, status, exception string) error {
	const q = `
INSERT INTO sys_job_log
  (job_name, job_group, job_executor, invoke_target, job_args, job_kwargs,
   job_trigger, job_message, status, exception_info, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
	_, err := s.db.ExecContext(ctx, q,
		row.JobName, row.JobGroup, row.JobExecutor, row.InvokeTarget,
		row.JobArgs, row.JobKwargs, trigger, message, status, exception, time.Now(),
	)
	return err
}
