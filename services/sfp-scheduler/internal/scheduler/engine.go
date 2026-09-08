package scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/cron"
	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/jobs"
	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/queue"
	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/store"
)

const (
	CommandChannel = "sfp:scheduler:command"
	SyncChannel    = "scheduler:sync:request"
	HeartbeatKey   = "sfp:scheduler:heartbeat"
	HeartbeatTTL   = 25 * time.Second
	LockKey        = "app:scheduler:lock"
	TimeLayout     = "2006-01-02 15:04:05"

	// Python sets misfire_grace_time=1e12 seconds when misfire_policy=="3"
	// (effectively always fire). int64 cannot hold that many seconds.
	policy3Grace = 100 * 365 * 24 * time.Hour
)

type scheduledJob struct {
	row      store.JobRow
	schedule *cron.Schedule
	next     time.Time
	spec     jobs.Spec
}

type HeartbeatJob struct {
	JobID       string  `json:"jobId"`
	Name        string  `json:"name"`
	NextRunTime *string `json:"nextRunTime"`
}

type Engine struct {
	cfg      config.Config
	store    *store.Store
	enqueuer *queue.Enqueuer
	redis    *redis.Client
	loc      *time.Location
	logger   *slog.Logger
	workerID string

	mu      sync.Mutex
	jobs    map[int64]*scheduledJob
	leader  bool
	running bool
}

func New(cfg config.Config, st *store.Store, rdb *redis.Client, loc *time.Location, logger *slog.Logger, workerID string) *Engine {
	return &Engine{
		cfg:      cfg,
		store:    st,
		enqueuer: queue.NewEnqueuer(rdb, loc),
		redis:    rdb,
		loc:      loc,
		logger:   logger,
		workerID: workerID,
		jobs:     map[int64]*scheduledJob{},
	}
}

func (e *Engine) IsLeader() bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.leader
}

func (e *Engine) Running() bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.running
}

func (e *Engine) JobCount() int {
	e.mu.Lock()
	defer e.mu.Unlock()
	return len(e.jobs)
}

func (e *Engine) QueueDepth(ctx context.Context) int64 {
	return e.enqueuer.Depth(ctx)
}

func (e *Engine) SnapshotJobs() []HeartbeatJob {
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]HeartbeatJob, 0, len(e.jobs))
	for id, job := range e.jobs {
		item := HeartbeatJob{JobID: fmt.Sprintf("%d", id), Name: job.row.JobName}
		if !job.next.IsZero() {
			s := job.next.In(e.loc).Format(TimeLayout)
			item.NextRunTime = &s
		}
		out = append(out, item)
	}
	return out
}

func (e *Engine) Run(ctx context.Context) error {
	if err := e.acquireLoop(ctx); err != nil && ctx.Err() == nil {
		return err
	}
	return ctx.Err()
}

func (e *Engine) acquireLoop(ctx context.Context) error {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		ok, err := e.tryAcquire(ctx)
		if err != nil {
			e.logger.Warn("scheduler lock acquire failed", "err", err)
		} else if ok {
			return e.lead(ctx)
		} else {
			e.setLeader(false)
			e.logger.Info("waiting for scheduler lock (Python or another Go instance may hold it)")
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}
	}
}

func (e *Engine) tryAcquire(ctx context.Context) (bool, error) {
	ok, err := e.redis.SetNX(ctx, LockKey, e.workerID, e.cfg.LockTTL).Result()
	if err != nil {
		return false, err
	}
	if ok {
		return true, nil
	}
	cur, err := e.redis.Get(ctx, LockKey).Result()
	if err == redis.Nil {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return cur == e.workerID, nil
}

func (e *Engine) lead(ctx context.Context) error {
	e.setLeader(true)
	e.logger.Info("acquired scheduler lock", "worker", e.workerID, "tz", e.loc.String())
	if err := e.Sync(ctx); err != nil {
		e.logger.Error("initial job sync failed", "err", err)
	}
	e.mu.Lock()
	e.running = true
	e.mu.Unlock()

	renew := time.NewTicker(e.cfg.LockRenewInterval)
	syncTick := time.NewTicker(e.cfg.SyncInterval)
	beat := time.NewTicker(e.cfg.HeartbeatInterval)
	fire := time.NewTicker(time.Second)
	defer renew.Stop()
	defer syncTick.Stop()
	defer beat.Stop()
	defer fire.Stop()

	cmdCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	go e.listenCommands(cmdCtx)

	_ = e.WriteHeartbeat(ctx)

	for {
		select {
		case <-ctx.Done():
			e.release(context.Background())
			return ctx.Err()
		case <-renew.C:
			if err := e.renewLock(ctx); err != nil {
				e.logger.Warn("lost scheduler lock", "err", err)
				e.setLeader(false)
				e.mu.Lock()
				e.running = false
				e.mu.Unlock()
				cancel()
				return e.acquireLoop(ctx)
			}
		case <-syncTick.C:
			if err := e.Sync(ctx); err != nil {
				e.logger.Warn("job sync failed", "err", err)
			}
		case <-beat.C:
			if err := e.WriteHeartbeat(ctx); err != nil {
				e.logger.Warn("heartbeat failed", "err", err)
			}
		case <-fire.C:
			e.fireDue(ctx, time.Now().In(e.loc))
		}
	}
}

func (e *Engine) renewLock(ctx context.Context) error {
	script := redis.NewScript(`
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("PEXPIRE", KEYS[1], ARGV[2])
end
return 0`)
	ok, err := script.Run(ctx, e.redis, []string{LockKey}, e.workerID, e.cfg.LockTTL.Milliseconds()).Int()
	if err != nil {
		return err
	}
	if ok == 0 {
		return fmt.Errorf("lock not owned")
	}
	return nil
}

func (e *Engine) release(ctx context.Context) {
	script := redis.NewScript(`
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0`)
	_ = script.Run(ctx, e.redis, []string{LockKey}, e.workerID).Err()
	e.setLeader(false)
	e.mu.Lock()
	e.running = false
	e.mu.Unlock()
}

func (e *Engine) setLeader(v bool) {
	e.mu.Lock()
	e.leader = v
	e.mu.Unlock()
}

func (e *Engine) Sync(ctx context.Context) error {
	rows, err := e.store.ListJobs(ctx)
	if err != nil {
		return err
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	seen := map[int64]struct{}{}
	now := time.Now().In(e.loc)
	for _, row := range rows {
		seen[row.JobID] = struct{}{}
		if row.Status != "0" {
			if _, ok := e.jobs[row.JobID]; ok {
				delete(e.jobs, row.JobID)
				e.logger.Info("paused job removed from schedule", "jobId", row.JobID, "name", row.JobName)
			}
			continue
		}
		spec, err := jobs.Resolve(row.InvokeTarget, row.JobArgs, row.JobKwargs)
		if err != nil {
			e.logger.Warn("skip unmapped job", "jobId", row.JobID, "target", row.InvokeTarget, "err", err)
			delete(e.jobs, row.JobID)
			continue
		}
		sched, err := cron.Parse(row.CronExpression, e.loc)
		if err != nil {
			e.logger.Warn("skip job with bad cron", "jobId", row.JobID, "cron", row.CronExpression, "err", err)
			delete(e.jobs, row.JobID)
			continue
		}
		cur, exists := e.jobs[row.JobID]
		if exists && sameSchedule(cur.row, row) {
			cur.row = row
			cur.spec = spec
			continue
		}
		next := sched.Next(now)
		e.jobs[row.JobID] = &scheduledJob{row: row, schedule: sched, next: next, spec: spec}
		if exists {
			e.logger.Info("updated job", "jobId", row.JobID, "cron", row.CronExpression, "next", next.Format(TimeLayout))
		} else {
			e.logger.Info("loaded job", "jobId", row.JobID, "name", row.JobName, "cron", row.CronExpression, "next", next.Format(TimeLayout))
		}
	}
	for id := range e.jobs {
		if _, ok := seen[id]; !ok {
			delete(e.jobs, id)
			e.logger.Info("removed deleted job", "jobId", id)
		}
	}
	return nil
}

func sameSchedule(a, b store.JobRow) bool {
	return a.CronExpression == b.CronExpression &&
		a.InvokeTarget == b.InvokeTarget &&
		a.JobArgs == b.JobArgs &&
		a.JobKwargs == b.JobKwargs &&
		a.MisfirePolicy == b.MisfirePolicy &&
		a.Status == b.Status
}

func misfireGrace(policy string) time.Duration {
	switch policy {
	case "3":
		// Match Python APScheduler: huge grace, fire even if very late.
		return policy3Grace
	case "2":
		// Coalesce: one fire for a missed window (cap 24h).
		return 24 * time.Hour
	default:
		// Policy 1 / other: Python sets misfire_grace_time=None (~1s default).
		return time.Second
	}
}

func (e *Engine) fireDue(ctx context.Context, now time.Time) {
	e.mu.Lock()
	defer e.mu.Unlock()
	for _, job := range e.jobs {
		if job.next.IsZero() || job.next.After(now) {
			continue
		}
		late := now.Sub(job.next)
		grace := misfireGrace(job.row.MisfirePolicy)
		if late > grace {
			e.logger.Info("misfire skipped", "jobId", job.row.JobID, "late", late.String(), "policy", job.row.MisfirePolicy)
		} else {
			e.enqueueLocked(ctx, job, "cron")
		}
		job.next = job.schedule.Next(now)
	}
}

func (e *Engine) enqueueLocked(ctx context.Context, job *scheduledJob, reason string) {
	queued, err := e.enqueuer.Enqueue(ctx, job.spec)
	if err != nil {
		e.logger.Error("enqueue failed", "jobId", job.row.JobID, "type", job.spec.JobType, "err", err)
		_ = e.store.InsertJobLog(ctx, job.row, job.row.CronExpression,
			fmt.Sprintf("事件类型: Enqueue, 任务ID: %d, 任务名称: %s, 执行于%s", job.row.JobID, job.row.JobName, time.Now().In(e.loc).Format(TimeLayout)),
			"1", err.Error())
		return
	}
	e.logger.Info("enqueued",
		"sysJobId", job.row.JobID,
		"type", queued.Type,
		"queue", queued.Queue,
		"jobId", queued.JobID,
		"reason", reason,
	)
	_ = e.store.InsertJobLog(ctx, job.row, job.row.CronExpression,
		fmt.Sprintf("事件类型: Enqueue, 任务ID: %d, 任务名称: %s, 执行于%s, queue=%s, type=%s, jobId=%s",
			job.row.JobID, job.row.JobName, time.Now().In(e.loc).Format(TimeLayout), queued.Queue, queued.Type, queued.JobID),
		"0", "")
}

func (e *Engine) RunOnce(ctx context.Context, jobID int64) error {
	row, err := e.store.GetJob(ctx, jobID)
	if err != nil {
		return err
	}
	spec, err := jobs.Resolve(row.InvokeTarget, row.JobArgs, row.JobKwargs)
	if err != nil {
		return err
	}
	e.mu.Lock()
	defer e.mu.Unlock()
	tmp := &scheduledJob{row: *row, spec: spec}
	if cur, ok := e.jobs[jobID]; ok {
		tmp.schedule = cur.schedule
	}
	e.enqueueLocked(ctx, tmp, "run")
	return nil
}

func (e *Engine) listenCommands(ctx context.Context) {
	for ctx.Err() == nil {
		pubsub := e.redis.Subscribe(ctx, CommandChannel, SyncChannel)
		ch := pubsub.Channel()
		e.logger.Info("listening for scheduler commands", "channels", []string{CommandChannel, SyncChannel})
	loop:
		for {
			select {
			case <-ctx.Done():
				_ = pubsub.Close()
				return
			case msg, ok := <-ch:
				if !ok {
					break loop
				}
				e.handleCommand(ctx, msg.Channel, msg.Payload)
			}
		}
		_ = pubsub.Close()
		time.Sleep(5 * time.Second)
	}
}

func (e *Engine) handleCommand(ctx context.Context, channel, raw string) {
	if channel == SyncChannel {
		if err := e.Sync(ctx); err != nil {
			e.logger.Warn("sync command failed", "err", err)
		}
		return
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(raw), &payload); err != nil {
		e.logger.Warn("ignore bad command", "raw", truncate(raw, 200))
		return
	}
	action, _ := payload["action"].(string)
	switch action {
	case "sync":
		if err := e.Sync(ctx); err != nil {
			e.logger.Warn("sync command failed", "err", err)
		}
	case "run":
		id, err := asInt64(payload["jobId"])
		if err != nil {
			e.logger.Warn("run command missing jobId")
			return
		}
		e.logger.Info("immediate run command", "jobId", id)
		if err := e.RunOnce(ctx, id); err != nil {
			e.logger.Warn("immediate run failed", "jobId", id, "err", err)
		}
	}
}

func (e *Engine) WriteHeartbeat(ctx context.Context) error {
	now := time.Now().In(e.loc).Format(TimeLayout)
	body := map[string]any{
		"alive":      true,
		"role":       "scheduler",
		"engine":     "sfp-scheduler",
		"workerId":   e.workerID,
		"pid":        os.Getpid(),
		"hostname":   hostname(),
		"queueDepth": e.enqueuer.Depth(ctx),
		"running":    []any{},
		"jobs":       e.SnapshotJobs(),
		"ts":         now,
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return err
	}
	return e.redis.Set(ctx, HeartbeatKey, raw, HeartbeatTTL).Err()
}

func hostname() string {
	h, err := os.Hostname()
	if err != nil {
		return "sfp-scheduler"
	}
	return h
}

func asInt64(v any) (int64, error) {
	switch n := v.(type) {
	case float64:
		return int64(n), nil
	case int64:
		return n, nil
	case int:
		return int64(n), nil
	case json.Number:
		return n.Int64()
	case string:
		var out int64
		_, err := fmt.Sscan(n, &out)
		return out, err
	default:
		return 0, fmt.Errorf("not an id")
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
