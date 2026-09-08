package opensync

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/bcrypt"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

const (
	syncTokenAud       = "open-sync"
	syncTokenScope     = "sync"
	syncTokenTTL       = 30 * time.Minute
	syncPageDefault    = 1000
	syncPageMax        = 2000
	syncTextTrim       = 16384
	syncRedisKeyPrefix = "sync_token"
	influxDataset      = "influx.daily"
)

var (
	identRE = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	dateRE  = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
	allowedMarkets = map[string]bool{"US": true, "CN": true, "HK": true}
)

var sensitiveColumns = map[string]bool{
	"password": true, "api_key": true, "apikey": true, "app_secret": true,
	"appsecret": true, "access_token": true, "accesstoken": true, "refresh_token": true,
	"private_key": true, "secret": true, "jwt": true, "feishu_token": true,
	"webhook": true, "webhook_url": true,
}

var forbiddenTables = map[string]bool{
	"quant_longbridge_config": true, "sys_user": true, "sys_user_role": true,
	"sys_logininfor": true, "ai_models": true, "plat_feishu_subscription": true,
	"plat_feishu_push": true,
}

type TableSpec struct {
	Name          string
	PK            string
	DateColumn    string
	MarketColumn  string
	TrimColumns   map[string]bool
}

var datasetTables = map[string][]TableSpec{
	"mysql.market": {
		{Name: "market_instrument", PK: "instrument_id", DateColumn: "create_time", MarketColumn: "market"},
		{Name: "market_price_history_daily", PK: "id", DateColumn: "trade_date", MarketColumn: "market"},
		{Name: "market_watchlist", PK: "id", DateColumn: "create_time", MarketColumn: "market"},
		{Name: "market_heat_daily", PK: "id", DateColumn: "trade_date", MarketColumn: "market"},
		{Name: "market_top50_snapshot", PK: "id", DateColumn: "trade_date", MarketColumn: "market"},
		{Name: "market_daily_review", PK: "review_id", DateColumn: "trade_date", MarketColumn: "market"},
	},
	"mysql.quant": {
		{Name: "quant_daily_list", PK: "list_id", DateColumn: "scan_date"},
		{Name: "quant_daily_list_item", PK: "item_id", DateColumn: "trade_date", MarketColumn: "market"},
		{Name: "quant_factor_snapshot", PK: "snapshot_id", DateColumn: "create_time", MarketColumn: "market"},
		{Name: "quant_readmodel_snapshot", PK: "snapshot_id", DateColumn: "create_time"},
	},
	"mysql.trade": {
		{Name: "plat_auto_trade_decision", PK: "decision_id", DateColumn: "create_time", MarketColumn: "market",
			TrimColumns: map[string]bool{"reason": true, "error": true}},
		{Name: "plat_ai_trade_run_log", PK: "run_id", DateColumn: "create_time",
			TrimColumns: map[string]bool{
				"guardrail_snapshot": true, "candidates_snapshot": true, "opportunities_snapshot": true,
				"skipped_reasons": true, "message": true,
			}},
	},
}

var datasetAliases = map[string]string{
	"market": "mysql.market", "mysql.market": "mysql.market",
	"quant": "mysql.quant", "mysql.quant": "mysql.quant",
	"trade": "mysql.trade", "mysql.trade": "mysql.trade",
	"influx": influxDataset, "influx.daily": influxDataset, "daily": influxDataset,
}

var tableByName = map[string]TableSpec{}

func init() {
	for _, specs := range datasetTables {
		for _, spec := range specs {
			tableByName[spec.Name] = spec
		}
	}
}

type Service struct {
	cfg   *config.Config
	db    *store.DB
	redis *redis.Client
}

func New(cfg *config.Config, db *store.DB, rdb *redis.Client) *Service {
	return &Service{cfg: cfg, db: db, redis: rdb}
}

func AvailableDatasets() []string {
	return []string{"mysql.market", "mysql.quant", "mysql.trade", influxDataset}
}

func (s *Service) IssueToken(ctx context.Context, username, password string) (map[string]interface{}, error) {
	userName := strings.TrimSpace(username)
	if userName == "" || password == "" {
		return nil, errService("用户名或密码不能为空")
	}
	user, err := s.db.GetUserByName(ctx, userName)
	if err != nil {
		return nil, err
	}
	if user == nil {
		return nil, errService("用户不存在")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(password)); err != nil {
		return nil, errService("密码错误")
	}
	if user.Status == "1" {
		return nil, errService("用户已停用")
	}
	bundle, err := s.db.GetUserBundle(ctx, user.UserID)
	if err != nil {
		return nil, err
	}
	if !isSyncAdmin(user.UserID, bundle) {
		return nil, errForbidden("仅管理员可同步数据")
	}
	sessionID := fmt.Sprintf("%d", time.Now().UnixNano())
	token, err := s.createSyncToken(user, sessionID)
	if err != nil {
		return nil, err
	}
	if s.redis != nil {
		_ = s.redis.Set(ctx, fmt.Sprintf("%s:%s", syncRedisKeyPrefix, sessionID), token, syncTokenTTL).Err()
	}
	return map[string]interface{}{
		"token":     token,
		"expiresIn": int(syncTokenTTL.Seconds()),
		"datasets":  AvailableDatasets(),
	}, nil
}

func isSyncAdmin(userID int64, bundle *store.UserBundle) bool {
	if userID == 1 {
		return true
	}
	if bundle != nil {
		for _, role := range bundle.Roles {
			if role.RoleID == 1 {
				return true
			}
		}
	}
	return false
}

func (s *Service) createSyncToken(user *store.SysUser, sessionID string) (string, error) {
	claims := jwt.MapClaims{
		"user_id":    fmt.Sprintf("%d", user.UserID),
		"user_name":  user.UserName,
		"session_id": sessionID,
		"scope":      syncTokenScope,
		"aud":        syncTokenAud,
		"exp":        time.Now().UTC().Add(syncTokenTTL).Unix(),
	}
	return jwt.NewWithClaims(jwt.GetSigningMethod(s.cfg.JWTAlgorithm), claims).SignedString([]byte(s.cfg.JWTSecret))
}

func (s *Service) VerifyPullToken(ctx context.Context, authorization string) (map[string]interface{}, error) {
	token := extractBearer(authorization)
	claims := jwt.MapClaims{}
	parsed, err := jwt.ParseWithClaims(token, claims, func(t *jwt.Token) (interface{}, error) {
		return []byte(s.cfg.JWTSecret), nil
	}, jwt.WithAudience(syncTokenAud))
	if err != nil || !parsed.Valid {
		return nil, errAuth("同步令牌已失效，请重新登录")
	}
	if claims["scope"] != syncTokenScope {
		return nil, errAuth("同步令牌范围无效")
	}
	if claims["user_id"] == nil || fmt.Sprint(claims["user_id"]) == "" {
		return nil, errAuth("同步令牌不合法")
	}
	sessionID := fmt.Sprint(claims["session_id"])
	if s.redis != nil && sessionID != "" {
		stored, err := s.redis.Get(ctx, fmt.Sprintf("%s:%s", syncRedisKeyPrefix, sessionID)).Result()
		if err == nil && stored != "" && stored != token {
			return nil, errAuth("同步令牌已失效，请重新登录")
		}
	}
	out := map[string]interface{}{}
	for k, v := range claims {
		out[k] = v
	}
	return out, nil
}

type PullRequest struct {
	Datasets []string
	Markets  []string
	Since    string
	Cursor   interface{}
	Limit    *int
}

func (s *Service) Pull(ctx context.Context, req PullRequest) (map[string]interface{}, error) {
	datasets, err := normalizeDatasets(req.Datasets)
	if err != nil {
		return nil, err
	}
	markets := normalizeMarkets(req.Markets)
	since, err := normalizeSince(req.Since)
	if err != nil {
		return nil, err
	}
	pageSize := clampPageSize(req.Limit)
	current, err := parseCursor(req.Cursor)
	if err != nil {
		return nil, err
	}
	if current == nil {
		current = initialCursor(datasets, markets)
	}
	dataset := fmt.Sprint(current["dataset"])
	if !contains(datasets, dataset) {
		return nil, errService("cursor 与 datasets 不匹配")
	}
	if dataset == influxDataset {
		return s.pullInflux(ctx, datasets, markets, since, current, pageSize)
	}
	return s.pullMySQL(ctx, datasets, markets, since, current, pageSize)
}

func (s *Service) pullMySQL(ctx context.Context, datasets, markets []string, since string, cursor map[string]interface{}, pageSize int) (map[string]interface{}, error) {
	dataset := fmt.Sprint(cursor["dataset"])
	table := fmt.Sprint(cursor["table"])
	if forbiddenTables[table] || tableByName[table].Name == "" {
		return nil, errService(fmt.Sprintf("拒绝同步表: %s", table))
	}
	spec := tableByName[table]
	lastPK := intFrom(cursor["pk"])
	rows, err := s.fetchTablePage(ctx, spec, lastPK, pageSize, markets, since)
	if err != nil {
		nxt := advanceMySQLCursor(datasets, cursor, lastPK, 0, pageSize, markets)
		return map[string]interface{}{
			"dataset": dataset, "table": table, "rows": []interface{}{}, "rowCount": 0,
			"nextCursor": nxt, "skipped": true, "reason": "表不存在或查询失败",
		}, nil
	}
	nextPK := lastPK
	if len(rows) > 0 {
		nextPK = intFrom(rows[len(rows)-1][spec.PK])
	}
	nxt := advanceMySQLCursor(datasets, cursor, nextPK, len(rows), pageSize, markets)
	return map[string]interface{}{
		"dataset": dataset, "table": table, "rows": rows, "rowCount": len(rows), "nextCursor": nxt,
	}, nil
}

func (s *Service) fetchTablePage(ctx context.Context, spec TableSpec, lastPK, pageSize int, markets []string, since string) ([]map[string]interface{}, error) {
	quotedTable := quoteIdent(spec.Name)
	quotedPK := quoteIdent(spec.PK)
	clauses := []string{fmt.Sprintf("%s > ?", quotedPK)}
	args := []interface{}{lastPK}
	if spec.MarketColumn != "" && len(markets) > 0 {
		ph := make([]string, len(markets))
		for i, m := range markets {
			ph[i] = "?"
			args = append(args, m)
		}
		clauses = append(clauses, fmt.Sprintf("%s IN (%s)", quoteIdent(spec.MarketColumn), strings.Join(ph, ",")))
	}
	if spec.DateColumn != "" && since != "" {
		clauses = append(clauses, fmt.Sprintf("%s >= ?", quoteIdent(spec.DateColumn)))
		args = append(args, since)
	}
	args = append(args, pageSize)
	sqlText := fmt.Sprintf("SELECT * FROM %s WHERE %s ORDER BY %s ASC LIMIT ?",
		quotedTable, strings.Join(clauses, " AND "), quotedPK)
	rows, err := s.db.QueryContext(ctx, sqlText, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	out := []map[string]interface{}{}
	for rows.Next() {
		raw := make([]interface{}, len(cols))
		ptrs := make([]interface{}, len(cols))
		for i := range raw {
			ptrs[i] = &raw[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		row := map[string]interface{}{}
		for i, col := range cols {
			row[col] = sanitizeValue(col, raw[i], spec.TrimColumns)
		}
		out = append(out, row)
	}
	return out, nil
}

func (s *Service) pullInflux(ctx context.Context, datasets, markets []string, since string, cursor map[string]interface{}, pageSize int) (map[string]interface{}, error) {
	market := strings.ToUpper(fmt.Sprint(cursor["market"]))
	if market == "" {
		market = markets[0]
	}
	if !allowedMarkets[market] {
		return nil, errService(fmt.Sprintf("不支持的市场: %s", market))
	}
	offset := intFrom(cursor["offset"])
	klines, reason := s.queryInfluxDaily(ctx, market, since, pageSize, offset)
	if reason != "" {
		nxt := advanceInfluxCursor(datasets, markets, map[string]interface{}{"dataset": influxDataset, "market": market, "offset": offset}, 0, pageSize)
		return map[string]interface{}{
			"dataset": influxDataset, "klines": []interface{}{}, "rowCount": 0,
			"nextCursor": nxt, "skipped": true, "reason": reason,
		}, nil
	}
	nxt := advanceInfluxCursor(datasets, markets, map[string]interface{}{"dataset": influxDataset, "market": market, "offset": offset}, len(klines), pageSize)
	return map[string]interface{}{
		"dataset": influxDataset, "market": market, "klines": klines, "rowCount": len(klines), "nextCursor": nxt,
	}, nil
}

func (s *Service) queryInfluxDaily(ctx context.Context, market, since string, pageSize, offset int) ([]map[string]interface{}, string) {
	if s.cfg.InfluxToken == "" || s.cfg.InfluxURL == "" {
		return nil, "Influx 未配置"
	}
	bucket := s.cfg.InfluxBucketCN
	if market == "US" {
		bucket = s.cfg.InfluxBucketUS
	}
	if !regexp.MustCompile(`^[A-Za-z0-9._-]{1,64}$`).MatchString(bucket) {
		return nil, "Influx bucket 非法"
	}
	startClause := "-2y"
	if since != "" {
		startClause = fmt.Sprintf(`time(v: "%sT00:00:00Z")`, since)
	}
	flux := fmt.Sprintf(`from(bucket: "%s")
  |> range(start: %s)
  |> filter(fn: (r) => r._measurement == "daily_kline")
  |> filter(fn: (r) => r.market == "%s")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time", "symbol"])
  |> limit(n: %d, offset: %d)`, bucket, startClause, market, pageSize, offset)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(s.cfg.InfluxURL, "/")+"/api/v2/query?org="+s.cfg.InfluxOrg, strings.NewReader(flux))
	if err != nil {
		return nil, "Influx 查询失败"
	}
	req.Header.Set("Authorization", "Token "+s.cfg.InfluxToken)
	req.Header.Set("Content-Type", "application/vnd.flux")
	req.Header.Set("Accept", "application/csv")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, "Influx 查询失败"
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, "Influx 查询失败"
	}
	body, _ := io.ReadAll(resp.Body)
	return parseInfluxCSV(body, market), ""
}

func parseInfluxCSV(body []byte, market string) []map[string]interface{} {
	lines := strings.Split(string(body), "\n")
	if len(lines) < 2 {
		return []map[string]interface{}{}
	}
	header := strings.Split(lines[0], ",")
	idx := map[string]int{}
	for i, h := range header {
		idx[strings.TrimSpace(h)] = i
	}
	out := []map[string]interface{}{}
	for _, line := range lines[1:] {
		if strings.TrimSpace(line) == "" {
			continue
		}
		parts := strings.Split(line, ",")
		get := func(name string) string {
			if i, ok := idx[name]; ok && i < len(parts) {
				return strings.TrimSpace(parts[i])
			}
			return ""
		}
		ts := get("_time")
		date := ""
		if len(ts) >= 10 {
			date = ts[:10]
		}
		out = append(out, map[string]interface{}{
			"market": market, "symbol": get("symbol"), "date": date,
			"open": get("open"), "high": get("high"), "low": get("low"),
			"close": get("close"), "volume": get("volume"),
		})
	}
	return out
}

func normalizeDatasets(raw []string) ([]string, error) {
	if len(raw) == 0 {
		return nil, errService("datasets 不能为空")
	}
	out := []string{}
	seen := map[string]bool{}
	for _, item := range raw {
		key := strings.TrimSpace(strings.ToLower(item))
		ds := datasetAliases[key]
		if ds == "" {
			ds = datasetAliases[strings.TrimSpace(item)]
		}
		if ds == "" {
			return nil, errService(fmt.Sprintf("不支持的数据集: %s", item))
		}
		if !seen[ds] {
			seen[ds] = true
			out = append(out, ds)
		}
	}
	if len(out) == 0 {
		return nil, errService("datasets 不能为空")
	}
	return out, nil
}

func normalizeMarkets(raw []string) []string {
	if len(raw) == 0 {
		return []string{"US", "CN", "HK"}
	}
	out := []string{}
	for _, item := range raw {
		m := strings.ToUpper(strings.TrimSpace(item))
		if !allowedMarkets[m] {
			continue
		}
		if !contains(out, m) {
			out = append(out, m)
		}
	}
	if len(out) == 0 {
		return []string{"US", "CN", "HK"}
	}
	return out
}

func normalizeSince(raw string) (string, error) {
	text := strings.TrimSpace(raw)
	if text == "" {
		return "", nil
	}
	if !dateRE.MatchString(text) {
		return "", errService("since 必须为 YYYY-MM-DD")
	}
	return text, nil
}

func clampPageSize(limit *int) int {
	if limit == nil {
		return syncPageDefault
	}
	if *limit < 1 {
		return syncPageDefault
	}
	if *limit > syncPageMax {
		return syncPageMax
	}
	return *limit
}

func parseCursor(cursor interface{}) (map[string]interface{}, error) {
	if cursor == nil {
		return nil, nil
	}
	switch v := cursor.(type) {
	case map[string]interface{}:
		return v, nil
	case string:
		text := strings.TrimSpace(v)
		if text == "" {
			return nil, nil
		}
		if strings.Contains(text, "|") {
			parts := strings.Split(text, "|")
			if len(parts) >= 3 {
				return map[string]interface{}{"dataset": parts[0], "table": parts[1], "pk": parts[2]}, nil
			}
		}
		if strings.Contains(text, ":") {
			parts := strings.SplitN(text, ":", 2)
			return map[string]interface{}{"table": parts[0], "pk": parts[1]}, nil
		}
		return nil, errService("cursor 格式不合法")
	default:
		return nil, errService("cursor 格式不合法")
	}
}

func initialCursor(datasets, markets []string) map[string]interface{} {
	ds := datasets[0]
	if ds == influxDataset {
		return map[string]interface{}{"dataset": ds, "market": markets[0], "offset": 0}
	}
	return map[string]interface{}{"dataset": ds, "table": datasetTables[ds][0].Name, "pk": 0}
}

func advanceMySQLCursor(datasets []string, cursor map[string]interface{}, lastPK, rowCount, pageSize int, markets []string) map[string]interface{} {
	dataset := fmt.Sprint(cursor["dataset"])
	table := fmt.Sprint(cursor["table"])
	if rowCount >= pageSize {
		return map[string]interface{}{"dataset": dataset, "table": table, "pk": lastPK}
	}
	specs := datasetTables[dataset]
	names := make([]string, len(specs))
	for i, s := range specs {
		names[i] = s.Name
	}
	index := indexOf(names, table)
	if index >= 0 && index+1 < len(names) {
		return map[string]interface{}{"dataset": dataset, "table": names[index+1], "pk": 0}
	}
	nxt := nextDataset(datasets, dataset)
	if nxt == "" {
		return nil
	}
	if nxt == influxDataset {
		return map[string]interface{}{"dataset": nxt, "market": markets[0], "offset": 0}
	}
	return map[string]interface{}{"dataset": nxt, "table": datasetTables[nxt][0].Name, "pk": 0}
}

func advanceInfluxCursor(datasets, markets []string, cursor map[string]interface{}, rowCount, pageSize int) map[string]interface{} {
	market := strings.ToUpper(fmt.Sprint(cursor["market"]))
	offset := intFrom(cursor["offset"]) + rowCount
	if rowCount >= pageSize {
		return map[string]interface{}{"dataset": influxDataset, "market": market, "offset": offset}
	}
	index := indexOf(markets, market)
	if index >= 0 && index+1 < len(markets) {
		return map[string]interface{}{"dataset": influxDataset, "market": markets[index+1], "offset": 0}
	}
	nxt := nextDataset(datasets, influxDataset)
	if nxt == "" {
		return nil
	}
	if nxt == influxDataset {
		return nil
	}
	return map[string]interface{}{"dataset": nxt, "table": datasetTables[nxt][0].Name, "pk": 0}
}

func nextDataset(datasets []string, current string) string {
	for i, ds := range datasets {
		if ds == current && i+1 < len(datasets) {
			return datasets[i+1]
		}
	}
	return ""
}

func quoteIdent(name string) string {
	if !identRE.MatchString(name) {
		panic(errService("非法数据表或字段名"))
	}
	return "`" + name + "`"
}

func sanitizeValue(column string, raw interface{}, trimCols map[string]bool) interface{} {
	lower := strings.ToLower(column)
	if sensitiveColumns[lower] {
		return nil
	}
	switch v := raw.(type) {
	case nil:
		return nil
	case []byte:
		s := string(v)
		if trimCols[lower] || len(s) > syncTextTrim {
			return trimText(s)
		}
		return s
	case time.Time:
		return v.Format("2006-01-02 15:04:05")
	case sql.NullString:
		if !v.Valid {
			return nil
		}
		if trimCols[lower] || len(v.String) > syncTextTrim {
			return trimText(v.String)
		}
		return v.String
	case sql.NullInt64:
		if !v.Valid {
			return nil
		}
		return v.Int64
	case sql.NullFloat64:
		if !v.Valid {
			return nil
		}
		return v.Float64
	case sql.NullTime:
		if !v.Valid {
			return nil
		}
		return v.Time.Format("2006-01-02 15:04:05")
	default:
		s := fmt.Sprint(v)
		if trimCols[lower] || len(s) > syncTextTrim {
			return trimText(s)
		}
		return v
	}
}

func trimText(s string) string {
	if len(s) <= syncTextTrim {
		return s
	}
	return s[:syncTextTrim] + "…"
}

func extractBearer(authorization string) string {
	raw := strings.TrimSpace(authorization)
	if strings.HasPrefix(strings.ToLower(raw), "bearer") {
		parts := strings.SplitN(raw, " ", 2)
		if len(parts) != 2 || strings.TrimSpace(parts[1]) == "" {
			panic(errAuth("同步令牌不合法"))
		}
		return strings.TrimSpace(parts[1])
	}
	if raw == "" {
		panic(errAuth("同步令牌不合法"))
	}
	return raw
}

func contains(list []string, item string) bool {
	for _, v := range list {
		if v == item {
			return true
		}
	}
	return false
}

func indexOf(list []string, item string) int {
	for i, v := range list {
		if v == item {
			return i
		}
	}
	return -1
}

func intFrom(v interface{}) int {
	switch x := v.(type) {
	case float64:
		return int(x)
	case int:
		return x
	case int64:
		return int(x)
	case string:
		var n int
		fmt.Sscanf(x, "%d", &n)
		return n
	default:
		return 0
	}
}

type serviceError struct{ msg string }
func errService(msg string) error { return &serviceError{msg: msg} }
func (e *serviceError) Error() string { return e.msg }

type authError struct{ msg string }
func errAuth(msg string) error { return &authError{msg: msg} }
func (e *authError) Error() string { return e.msg }

type forbiddenError struct{ msg string }
func errForbidden(msg string) error { return &forbiddenError{msg: msg} }
func (e *forbiddenError) Error() string { return e.msg }

func IsAuthError(err error) bool {
	var e *authError
	return errors.As(err, &e)
}

func IsForbiddenError(err error) bool {
	var e *forbiddenError
	return errors.As(err, &e)
}

func IsServiceError(err error) bool {
	var e *serviceError
	return errors.As(err, &e)
}
