package store

import (
	"context"
	"database/sql"
	"sort"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/timeutil"
)

type DictDataRow struct {
	DictCode  int64  `json:"dictCode"`
	DictSort  int    `json:"dictSort"`
	DictLabel string `json:"dictLabel"`
	DictValue string `json:"dictValue"`
	DictType  string `json:"dictType"`
	CSSClass  string `json:"cssClass"`
	ListClass string `json:"listClass"`
	IsDefault string `json:"isDefault"`
	Status    string `json:"status"`
}

func (db *DB) ListDictDataByType(ctx context.Context, dictType string) ([]DictDataRow, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT d.dict_code, d.dict_sort, d.dict_label, d.dict_value, d.dict_type,
		       IFNULL(d.css_class,''), IFNULL(d.list_class,''), IFNULL(d.is_default,'N'), d.status
		FROM sys_dict_type t
		JOIN sys_dict_data d ON t.dict_type = d.dict_type AND d.status = '0'
		WHERE t.dict_type = ? AND t.status = '0'
		ORDER BY d.dict_sort`, dictType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []DictDataRow
	for rows.Next() {
		var row DictDataRow
		if err := rows.Scan(&row.DictCode, &row.DictSort, &row.DictLabel, &row.DictValue, &row.DictType,
			&row.CSSClass, &row.ListClass, &row.IsDefault, &row.Status); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func (db *DB) GetConfigValue(ctx context.Context, configKey string) (string, error) {
	var value string
	err := db.QueryRowContext(ctx, `
		SELECT config_value FROM sys_config WHERE config_key = ? AND status = '0' LIMIT 1`, configKey).Scan(&value)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return value, err
}

type SysJobRow struct {
	JobID          int64
	JobName        string
	InvokeTarget   string
	CronExpression string
	Status         string
	Remark         sql.NullString
}

func (db *DB) GetJobsByIDs(ctx context.Context, ids []int) (map[int64]SysJobRow, error) {
	if len(ids) == 0 {
		return map[int64]SysJobRow{}, nil
	}
	placeholders := strings.TrimRight(strings.Repeat("?,", len(ids)), ",")
	args := make([]interface{}, len(ids))
	for i, id := range ids {
		args[i] = id
	}
	rows, err := db.QueryContext(ctx, `
		SELECT job_id, job_name, invoke_target, IFNULL(cron_expression,''), IFNULL(status,'1'), remark
		FROM sys_job WHERE job_id IN (`+placeholders+`)`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64]SysJobRow{}
	for rows.Next() {
		var row SysJobRow
		if err := rows.Scan(&row.JobID, &row.JobName, &row.InvokeTarget, &row.CronExpression, &row.Status, &row.Remark); err != nil {
			return nil, err
		}
		out[row.JobID] = row
	}
	return out, rows.Err()
}

func (db *DB) GetJobByID(ctx context.Context, jobID int64) (*SysJobRow, error) {
	var row SysJobRow
	err := db.QueryRowContext(ctx, `
		SELECT job_id, job_name, invoke_target, IFNULL(cron_expression,''), IFNULL(status,'1'), remark
		FROM sys_job WHERE job_id = ? LIMIT 1`, jobID).Scan(
		&row.JobID, &row.JobName, &row.InvokeTarget, &row.CronExpression, &row.Status, &row.Remark)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &row, nil
}

func (db *DB) UpdateJobStatus(ctx context.Context, jobID int64, status string) error {
	_, err := db.ExecContext(ctx, `UPDATE sys_job SET status = ?, update_time = ? WHERE job_id = ?`,
		status, time.Now(), jobID)
	return err
}

type JobLogRow struct {
	CreateTime    string `json:"createTime"`
	Status        string `json:"status"`
	JobMessage    string `json:"jobMessage"`
	ExceptionInfo string `json:"exceptionInfo"`
}

func (db *DB) ListJobLogs(ctx context.Context, jobName string, pageNum, pageSize int) ([]JobLogRow, int, error) {
	if pageNum <= 0 {
		pageNum = 1
	}
	if pageSize <= 0 {
		pageSize = 20
	}
	var total int
	if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sys_job_log WHERE job_name = ?`, jobName).Scan(&total); err != nil {
		return nil, 0, err
	}
	offset := (pageNum - 1) * pageSize
	rows, err := db.QueryContext(ctx, `
		SELECT create_time, status, IFNULL(job_message,''), IFNULL(exception_info,'')
		FROM sys_job_log WHERE job_name = ? ORDER BY create_time DESC LIMIT ? OFFSET ?`,
		jobName, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	var out []JobLogRow
	for rows.Next() {
		var row JobLogRow
		var createTime sql.NullTime
		if err := rows.Scan(&createTime, &row.Status, &row.JobMessage, &row.ExceptionInfo); err != nil {
			return nil, 0, err
		}
		if createTime.Valid {
			row.CreateTime = timeutil.FormatBeijing(createTime.Time)
		}
		out = append(out, row)
	}
	return out, total, rows.Err()
}

func (db *DB) LatestJobLogsByNames(ctx context.Context, names []string) (map[string]JobLogRow, error) {
	out := map[string]JobLogRow{}
	for _, name := range names {
		if strings.TrimSpace(name) == "" {
			continue
		}
		var row JobLogRow
		var createTime sql.NullTime
		err := db.QueryRowContext(ctx, `
			SELECT create_time, status, IFNULL(job_message,''), IFNULL(exception_info,'')
			FROM sys_job_log WHERE job_name = ? ORDER BY create_time DESC LIMIT 1`, name).Scan(
			&createTime, &row.Status, &row.JobMessage, &row.ExceptionInfo)
		if err == sql.ErrNoRows {
			continue
		}
		if err != nil {
			return nil, err
		}
		if createTime.Valid {
			row.CreateTime = timeutil.FormatBeijing(createTime.Time)
		}
		out[name] = row
	}
	return out, nil
}

func (db *DB) CountTodayJobLogs(ctx context.Context, names []string) (success int, failed int, err error) {
	if len(names) == 0 {
		return 0, 0, nil
	}
	placeholders := strings.TrimRight(strings.Repeat("?,", len(names)), ",")
	args := make([]interface{}, len(names))
	for i, name := range names {
		args[i] = name
	}
	start := timeutil.TodayBeijingStart()
	var okCount, failCount int
	err = db.QueryRowContext(ctx, `
		SELECT
			SUM(CASE WHEN status = '0' THEN 1 ELSE 0 END),
			SUM(CASE WHEN status = '1' THEN 1 ELSE 0 END)
		FROM sys_job_log
		WHERE job_name IN (`+placeholders+`) AND create_time >= ?`, append(args, start)...).Scan(&okCount, &failCount)
	if err != nil {
		return 0, 0, err
	}
	return okCount, failCount, nil
}

func (db *DB) CountJobLogsSince(ctx context.Context, since time.Time) (total int, failed int, err error) {
	err = db.QueryRowContext(ctx, `
		SELECT COUNT(*), SUM(CASE WHEN status = '1' THEN 1 ELSE 0 END)
		FROM sys_job_log WHERE create_time >= ?`, since).Scan(&total, &failed)
	return total, failed, err
}

func (db *DB) LatestJobLog(ctx context.Context) (name, status, createTime string, err error) {
	var jobName, st string
	var ct sql.NullTime
	err = db.QueryRowContext(ctx, `
		SELECT job_name, status, create_time FROM sys_job_log ORDER BY create_time DESC LIMIT 1`).Scan(&jobName, &st, &ct)
	if err == sql.ErrNoRows {
		return "", "", "", nil
	}
	if err != nil {
		return "", "", "", err
	}
	if ct.Valid {
		createTime = timeutil.FormatBeijing(ct.Time)
	}
	return jobName, st, createTime, nil
}

func (db *DB) ListExtraAnalysisJobs(ctx context.Context, known map[int]bool) ([]SysJobRow, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT job_id, job_name, invoke_target, IFNULL(cron_expression,''), IFNULL(status,'1'), remark
		FROM sys_job
		WHERE invoke_target LIKE 'module_task.%'
		   OR invoke_target IN (`+goInvokeTargetSQLIn()+`)
		ORDER BY job_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []SysJobRow
	for rows.Next() {
		var row SysJobRow
		if err := rows.Scan(&row.JobID, &row.JobName, &row.InvokeTarget, &row.CronExpression, &row.Status, &row.Remark); err != nil {
			return nil, err
		}
		if known[int(row.JobID)] {
			continue
		}
		if !isAnalysisTarget(row.InvokeTarget) {
			continue
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func isAnalysisTarget(target string) bool {
	if _, ok := analysisGoInvokeTargets[target]; ok {
		return true
	}
	if !strings.HasPrefix(target, "module_task.") || strings.Contains(target, "scheduler_test") {
		return false
	}
	for _, mod := range []string{"market_task", "quant_task", "sentiment_task", "trade_task"} {
		if strings.Contains(target, "."+mod+".") {
			return true
		}
	}
	return false
}

// analysisGoInvokeTargets maps bare Redis job types to analysis UI categories.
var analysisGoInvokeTargets = map[string]string{
	"sentiment_collect": "sentiment", "sentiment_analyze": "sentiment",
	"market_sync": "market", "finance_briefings": "market", "symbol_content": "market",
	"market_heat_collect": "market", "eod_kline_sync": "market", "listings_sync": "market",
	"klines_slow": "market", "board_warmup": "market", "mysql_to_influx": "market",
	"watchlist_analyze": "market", "stock_pick_run": "market", "market_review": "market",
	"factor_scan": "quant", "factor_qc": "quant", "indicator_refresh": "quant",
	"strategy_run": "quant", "position_monitor": "quant", "daily_list_scan": "quant",
	"daily_list_open": "trade", "auto_trade_scan": "trade",
	"feishu_push": "trade",
	"daily_review": "sentiment", "req_send": "sentiment", "req_summarize": "sentiment",
	"ai_analyze": "sentiment", "ai_batch": "sentiment", "user_notice": "sentiment",
}

func goInvokeTargetSQLIn() string {
	keys := make([]string, 0, len(analysisGoInvokeTargets))
	for key := range analysisGoInvokeTargets {
		keys = append(keys, "'"+key+"'")
	}
	sort.Strings(keys)
	return strings.Join(keys, ",")
}

func categoryFromTarget(target string) string {
	if cat, ok := analysisGoInvokeTargets[target]; ok {
		return cat
	}
	for mod, cat := range map[string]string{
		"market_task": "market", "quant_task": "quant", "sentiment_task": "sentiment", "trade_task": "trade",
	} {
		if strings.Contains(target, "."+mod+".") {
			return cat
		}
	}
	return "market"
}

func (db *DB) GetLatestHeat(ctx context.Context, market string) (map[string]interface{}, error) {
	var tradeDate, indexName sql.NullString
	var indexChange, turnover sql.NullFloat64
	var advance, decline, flat sql.NullInt64
	var heatScore sql.NullFloat64
	var asOfTime sql.NullTime
	err := db.QueryRowContext(ctx, `
		SELECT trade_date, index_name, index_change_pct, total_turnover,
		       advance_count, decline_count, flat_count, heat_score, as_of_time
		FROM market_heat_daily WHERE market = ? ORDER BY trade_date DESC LIMIT 1`, market).Scan(
		&tradeDate, &indexName, &indexChange, &turnover, &advance, &decline, &flat, &heatScore, &asOfTime)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	out := map[string]interface{}{
		"tradeDate": heatNullStr(tradeDate), "indexName": heatNullStr(indexName),
		"indexChangePct": heatNullFloat(indexChange), "totalTurnover": heatNullFloat(turnover),
		"advanceCount": heatNullInt(advance), "declineCount": heatNullInt(decline), "flatCount": heatNullInt(flat),
		"heatScore": heatNullFloat(heatScore),
	}
	if asOfTime.Valid {
		out["asOfTime"] = timeutil.FormatBeijing(asOfTime.Time)
	}
	return out, nil
}

func (db *DB) ListFinanceBriefings(ctx context.Context, limit int) ([]map[string]interface{}, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT market, briefing_type, headline, IFNULL(summary,''), IFNULL(source_name,''),
		       IFNULL(source_link,''), generated_at
		FROM finance_briefing ORDER BY generated_at DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []map[string]interface{}
	for rows.Next() {
		var market, briefingType, headline, summary, sourceName, sourceLink string
		var generatedAt sql.NullTime
		if err := rows.Scan(&market, &briefingType, &headline, &summary, &sourceName, &sourceLink, &generatedAt); err != nil {
			return nil, err
		}
		item := map[string]interface{}{
			"market": market, "briefingType": briefingType, "headline": headline,
			"summary": truncate(summary, 160), "sourceName": sourceName, "sourceLink": sourceLink,
		}
		if generatedAt.Valid {
			item["generatedAt"] = timeutil.FormatBeijing(generatedAt.Time)
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

func (db *DB) SentimentStats(ctx context.Context) (map[string]int, error) {
	stats := map[string]int{"total": 0, "today": 0, "unanalyzed": 0}
	var total int
	if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sentiment_news`).Scan(&total); err != nil {
		return nil, err
	}
	stats["total"] = total
	start := timeutil.TodayBeijingStart()
	var today int
	if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sentiment_news WHERE create_time >= ?`, start).Scan(&today); err != nil {
		return nil, err
	}
	stats["today"] = today
	var unanalyzed int
	if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sentiment_news WHERE analyzed = '0'`).Scan(&unanalyzed); err != nil {
		return nil, err
	}
	stats["unanalyzed"] = unanalyzed
	return stats, nil
}

func (db *DB) LatestSentimentAnalysis(ctx context.Context) (map[string]interface{}, error) {
	var id int64
	var title, summary, stance sql.NullString
	var createTime sql.NullTime
	err := db.QueryRowContext(ctx, `
		SELECT analysis_id, title, summary, stance, create_time
		FROM sentiment_analysis ORDER BY create_time DESC LIMIT 1`).Scan(&id, &title, &summary, &stance, &createTime)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	out := map[string]interface{}{"analysisId": id}
	if title.Valid {
		out["title"] = title.String
	}
	if summary.Valid {
		out["summary"] = summary.String
	}
	if stance.Valid {
		out["stance"] = stance.String
	}
	if createTime.Valid {
		out["createTime"] = timeutil.FormatBeijing(createTime.Time)
	}
	return out, nil
}

type WatchlistSignal struct {
	Symbol, Market, Name, Stance, Recommendation, Summary, AnalysisTime string
	Confidence                                                         *int
	Last, ChangeRate                                                   *float64
}

func (db *DB) WatchlistOverview(ctx context.Context, userID int64) (count, bullish, bearish, neutral int, signals []WatchlistSignal, err error) {
	rows, err := db.QueryContext(ctx, `
		SELECT w.symbol, IFNULL(w.market,'US'), IFNULL(w.name,''), a.stance, a.recommendation,
		       a.confidence, IFNULL(a.summary,''), a.price, a.change_percent, a.analysis_time
		FROM market_watchlist w
		LEFT JOIN market_watchlist_analysis a ON a.watchlist_id = w.watchlist_id
			AND a.analysis_id = (
				SELECT MAX(a2.analysis_id) FROM market_watchlist_analysis a2
				WHERE a2.watchlist_id = w.watchlist_id
			)
		WHERE w.user_id = ? AND w.enabled = '1'
		ORDER BY w.sort_order, w.watchlist_id`, userID)
	if err != nil {
		return 0, 0, 0, 0, nil, err
	}
	defer rows.Close()
	var items []WatchlistSignal
	for rows.Next() {
		var item WatchlistSignal
		var confidence sql.NullInt64
		var price, change sql.NullFloat64
		var analysisTime sql.NullTime
		if err := rows.Scan(&item.Symbol, &item.Market, &item.Name, &item.Stance, &item.Recommendation,
			&confidence, &item.Summary, &price, &change, &analysisTime); err != nil {
			return 0, 0, 0, 0, nil, err
		}
		if confidence.Valid {
			c := int(confidence.Int64)
			item.Confidence = &c
		}
		if price.Valid {
			v := price.Float64
			item.Last = &v
		}
		if change.Valid {
			v := change.Float64
			item.ChangeRate = &v
		}
		if analysisTime.Valid {
			item.AnalysisTime = timeutil.FormatBeijing(analysisTime.Time)
		}
		switch item.Stance {
		case "偏多":
			bullish++
		case "偏空":
			bearish++
		case "中性":
			neutral++
		}
		items = append(items, item)
	}
	count = len(items)
	signals = topWatchSignals(items, 5)
	return count, bullish, bearish, neutral, signals, rows.Err()
}

func topWatchSignals(items []WatchlistSignal, n int) []WatchlistSignal {
	rank := map[string]int{"偏多": 0, "偏空": 1, "中性": 2}
	sorted := append([]WatchlistSignal{}, items...)
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			a, b := sorted[i], sorted[j]
			ar := rank[a.Stance]
			if _, ok := rank[a.Stance]; !ok {
				ar = 3
			}
			br := rank[b.Stance]
			if _, ok := rank[b.Stance]; !ok {
				br = 3
			}
			ac := -1
			if a.Confidence != nil {
				ac = *a.Confidence
			}
			bc := -1
			if b.Confidence != nil {
				bc = *b.Confidence
			}
			if ar > br || (ar == br && ac < bc) {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}
	if len(sorted) > n {
		sorted = sorted[:n]
	}
	for i := range sorted {
		sorted[i].Summary = truncate(sorted[i].Summary, 120)
	}
	return sorted
}

func heatNullStr(v sql.NullString) interface{} {
	if v.Valid {
		return v.String
	}
	return nil
}

func heatNullFloat(v sql.NullFloat64) interface{} {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func heatNullInt(v sql.NullInt64) interface{} {
	if v.Valid {
		return v.Int64
	}
	return nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func IsAnalysisTarget(target string) bool { return isAnalysisTarget(target) }

func CategoryFromTarget(target string) string { return categoryFromTarget(target) }
