package analysis

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/scheduler"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

type Service struct {
	db       *store.DB
	sched    *scheduler.Runtime
	command  *scheduler.Commander
	appRole  string
}

func New(db *store.DB, sched *scheduler.Runtime, cmd *scheduler.Commander, appRole string) *Service {
	return &Service{db: db, sched: sched, command: cmd, appRole: appRole}
}

func (s *Service) Overview(ctx context.Context) (map[string]interface{}, error) {
	heartbeat, _ := s.sched.ReadHeartbeat(ctx)
	alive := scheduler.IsAlive(heartbeat)
	nextRun := map[string]interface{}{}
	if heartbeat != nil {
		if jobs, ok := heartbeat["jobs"].([]interface{}); ok {
			for _, item := range jobs {
				if m, ok := item.(map[string]interface{}); ok {
					id := fmt.Sprint(m["jobId"])
					nextRun[id] = m["nextRunTime"]
				}
			}
		}
	}
	ids := make([]int, 0, len(Catalog))
	known := map[int]bool{}
	for _, spec := range Catalog {
		ids = append(ids, spec.JobID)
		known[spec.JobID] = true
	}
	dbJobs, err := s.db.GetJobsByIDs(ctx, ids)
	if err != nil {
		return nil, err
	}
	extraJobs, err := s.db.ListExtraAnalysisJobs(ctx, known)
	if err != nil {
		return nil, err
	}
	logNames := make([]string, 0, len(Catalog)+len(extraJobs))
	for _, spec := range Catalog {
		logNames = append(logNames, spec.Title)
	}
	for _, job := range extraJobs {
		logNames = append(logNames, job.JobName)
	}
	latestLogs, err := s.db.LatestJobLogsByNames(ctx, logNames)
	if err != nil {
		return nil, err
	}
	todaySuccess, todayFailed, err := s.db.CountTodayJobLogs(ctx, logNames)
	if err != nil {
		return nil, err
	}

	jobs := make([]map[string]interface{}, 0, len(Catalog)+len(extraJobs))
	enabledCount, pausedCount, missingCount := 0, 0, 0
	for _, spec := range Catalog {
		dbJob := dbJobs[int64(spec.JobID)]
		status := "missing"
		if dbJob.JobID > 0 && dbJob.Status != "" {
			status = dbJob.Status
		}
		switch status {
		case "0":
			enabledCount++
		case "1":
			pausedCount++
		default:
			missingCount++
		}
		log := latestLogs[spec.Title]
		if dbJob.JobName != "" {
			if alt, ok := latestLogs[dbJob.JobName]; ok {
				log = alt
			}
		}
		cron := spec.DefaultCron
		if dbJob.CronExpression != "" {
			cron = dbJob.CronExpression
		}
		jobs = append(jobs, buildJobRow(spec, dbJob, status, cron, log, nextRun))
	}
	for _, job := range extraJobs {
		status := job.Status
		if status == "0" {
			enabledCount++
		} else {
			pausedCount++
		}
		log := latestLogs[job.JobName]
		jobs = append(jobs, map[string]interface{}{
			"jobId": int(job.JobID), "code": fmt.Sprintf("custom_%d", job.JobID),
			"category": store.CategoryFromTarget(job.InvokeTarget),
			"categoryLabel": CategoryLabel(store.CategoryFromTarget(job.InvokeTarget)),
			"title": job.JobName, "description": nullableRemark(job.Remark, "平台自动分析任务"),
			"invokeTarget": job.InvokeTarget, "cronExpression": job.CronExpression,
			"scheduleLabel": HumanizeCron(job.CronExpression), "status": status, "registered": true,
			"heavy": true, "queueType": nil, "remark": nullableRemark(job.Remark, ""),
			"lastRunTime": log.CreateTime, "lastRunStatus": nullableStatus(log.Status),
			"lastRunMessage": nullableMessage(log), "nextRunTime": nextRun[fmt.Sprint(job.JobID)],
		})
	}
	running := []interface{}{}
	queueDepth := 0
	if alive {
		if raw, ok := heartbeat["running"].([]interface{}); ok {
			running = raw
		}
		if v, ok := heartbeat["queueDepth"]; ok {
			switch x := v.(type) {
			case float64:
				queueDepth = int(x)
			case int:
				queueDepth = x
			}
		}
	} else {
		queueDepth = s.sched.QueueDepth(ctx)
	}
	return map[string]interface{}{
		"schedulerAlive": alive, "appRole": s.appRole,
		"workerId": heartbeatValue(heartbeat, "workerId"),
		"hostname": heartbeatValue(heartbeat, "hostname"),
		"pid":      heartbeatValue(heartbeat, "pid"),
		"heartbeatAt": heartbeatValue(heartbeat, "ts"),
		"queueDepth": queueDepth, "running": running,
		"enabledCount": enabledCount, "pausedCount": pausedCount, "missingCount": missingCount,
		"todaySuccess": todaySuccess, "todayFailed": todayFailed, "jobs": jobs,
	}, nil
}

func buildJobRow(spec JobSpec, dbJob store.SysJobRow, status, cron string, log store.JobLogRow, nextRun map[string]interface{}) map[string]interface{} {
	displayStatus := status
	if status == "missing" {
		displayStatus = "1"
	}
	return map[string]interface{}{
		"jobId": spec.JobID, "code": spec.Code, "category": spec.Category,
		"categoryLabel": CategoryLabel(spec.Category), "title": spec.Title, "description": spec.Description,
		"invokeTarget": spec.InvokeTarget, "cronExpression": cron,
		"scheduleLabel": HumanizeCron(cron), "status": displayStatus,
		"registered": dbJob.JobID > 0, "heavy": spec.Heavy, "queueType": spec.QueueType,
		"remark": nullableRemark(dbJob.Remark, spec.Description),
		"lastRunTime": nullableString(log.CreateTime), "lastRunStatus": nullableStatus(log.Status),
		"lastRunMessage": nullableMessage(log), "nextRunTime": nextRun[fmt.Sprint(spec.JobID)],
	}
}

func (s *Service) ChangeStatus(ctx context.Context, jobID int64, status string) error {
	if status != "0" && status != "1" {
		return fmt.Errorf("状态仅支持 0 启用 / 1 暂停")
	}
	if _, err := s.requireJob(ctx, jobID); err != nil {
		return err
	}
	return s.db.UpdateJobStatus(ctx, jobID, status)
}

func (s *Service) RunOnce(ctx context.Context, jobID int64) (string, error) {
	if _, err := s.requireJob(ctx, jobID); err != nil {
		return "", err
	}
	heartbeat, _ := s.sched.ReadHeartbeat(ctx)
	if !scheduler.IsAlive(heartbeat) {
		return "", fmt.Errorf("jobs 调度进程未在线。任务已从平台 API 进程拆出，请先启动 sfp-scheduler")
	}
	if err := s.command.PublishRun(ctx, jobID); err != nil {
		return "", fmt.Errorf("无法通知分析调度服务，请检查 Redis 连接")
	}
	return "已提交到分析调度微服务", nil
}

func (s *Service) Logs(ctx context.Context, jobID int64, pageNum, pageSize int) (map[string]interface{}, error) {
	job, err := s.requireJob(ctx, jobID)
	if err != nil {
		return nil, err
	}
	spec := ByID[int(jobID)]
	jobName := spec.Title
	if job != nil && job.JobName != "" {
		jobName = job.JobName
	}
	rows, total, err := s.db.ListJobLogs(ctx, jobName, pageNum, pageSize)
	if err != nil {
		return nil, err
	}
	hasNext := pageNum*pageSize < total
	return map[string]interface{}{
		"rows": rows, "total": total, "pageNum": pageNum, "pageSize": pageSize, "hasNext": hasNext,
	}, nil
}

func (s *Service) requireJob(ctx context.Context, jobID int64) (*store.SysJobRow, error) {
	spec := ByID[int(jobID)]
	job, err := s.db.GetJobByID(ctx, jobID)
	if err != nil {
		return nil, err
	}
	if job != nil && store.IsAnalysisTarget(job.InvokeTarget) {
		return job, nil
	}
	if spec.JobID > 0 {
		if job == nil {
			return nil, fmt.Errorf("任务未注册到 sys_job：%s，请先执行 sql/analysis-scheduler.sql", spec.Title)
		}
		return job, nil
	}
	return nil, fmt.Errorf("不是平台自动分析任务")
}

func heartbeatValue(heartbeat map[string]interface{}, key string) interface{} {
	if heartbeat == nil {
		return nil
	}
	return heartbeat[key]
}

func nullableRemark(v sql.NullString, fallback string) string {
	if v.Valid && v.String != "" {
		return v.String
	}
	return fallback
}

func nullableString(v string) interface{} {
	if v == "" {
		return nil
	}
	return v
}

func nullableStatus(v string) interface{} {
	if v == "" {
		return nil
	}
	return v
}

func nullableMessage(log store.JobLogRow) interface{} {
	if log.JobMessage != "" {
		return log.JobMessage
	}
	if log.ExceptionInfo != "" {
		return log.ExceptionInfo
	}
	return nil
}
