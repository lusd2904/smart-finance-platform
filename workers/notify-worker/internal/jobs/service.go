package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/go-sql-driver/mysql"

	mwcfg "github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/llm"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/newscollect"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/timeutil"
)

type Service struct {
	db     *sql.DB
	cfg    mwcfg.Config
	llm    *llm.Client
	influx *influx.Reader
	rss    *newscollect.Client
}

func NewService(cfg mwcfg.Config) (*Service, error) {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=true&loc=Local",
		cfg.MySQLUser, cfg.MySQLPassword, cfg.MySQLHost, cfg.MySQLPort, cfg.MySQLDatabase)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &Service{db: db, cfg: cfg, llm: llm.NewClient()}, nil
}

func (s *Service) Close() error { return s.db.Close() }

func (s *Service) Handle(ctx context.Context, jobType string, payload map[string]interface{}) (map[string]interface{}, error) {
	switch jobType {
	case "feishu_push":
		return nil, fmt.Errorf("feishu_push handled by store service")
	case "user_notice":
		return s.RunUserNotice(ctx, payload)
	case "sentiment_analyze":
		return s.RunSentimentAnalyze(ctx)
	case "sentiment_collect":
		return s.RunSentimentCollect(ctx, payload)
	case "daily_review":
		p := map[string]interface{}{"analyze": true}
		for k, v := range payload {
			p[k] = v
		}
		return s.RunSentimentCollect(ctx, p)
	case "req_send":
		return s.RunReqSend(ctx, payload, false)
	case "req_summarize":
		return s.RunReqSend(ctx, payload, true)
	case "watchlist_analyze":
		return s.RunWatchlistAnalyze(ctx, payload)
	case "stock_pick_run":
		return s.RunStockPick(ctx, payload)
	case "market_review":
		return s.RunMarketReview(ctx, payload)
	case "ai_analyze":
		return s.RunAIAnalyze(ctx, payload)
	case "ai_batch":
		return s.RunAIBatch(ctx, payload)
	default:
		return nil, fmt.Errorf("unsupported llm job type: %s", jobType)
	}
}

func nowBeijing() time.Time {
	return timeutil.NowShanghai()
}

func formatBeijing(t time.Time) string {
	return timeutil.FormatShanghai(t)
}

func intFrom(v interface{}) int64 {
	switch n := v.(type) {
	case float64:
		return int64(n)
	case int:
		return int64(n)
	case int64:
		return n
	case string:
		var out int64
		fmt.Sscan(n, &out)
		return out
	default:
		return 0
	}
}

func stringFrom(v interface{}) string {
	if v == nil {
		return ""
	}
	return fmt.Sprint(v)
}

func boolFrom(v interface{}, fallback bool) bool {
	if v == nil {
		return fallback
	}
	switch b := v.(type) {
	case bool:
		return b
	case string:
		return b == "1" || b == "true"
	case float64:
		return b != 0
	default:
		return fallback
	}
}
