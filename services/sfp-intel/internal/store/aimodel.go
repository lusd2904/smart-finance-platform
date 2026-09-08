package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

const maskedAPIKey = "********************************************************"

type AiModelDetail struct {
	ModelID          int64
	ModelCode        string
	ModelName        string
	Provider         string
	ModelSort        int
	Scope            string
	APIKeyEnc        string
	APIKey           string
	BaseURL          string
	ModelType        string
	MaxTokens        int
	Temperature      float64
	SupportReasoning string
	SupportImages    string
	Status           string
	UserID           sql.NullInt64
	DeptID           sql.NullInt64
	CreateBy         string
	CreateTime       *time.Time
	UpdateBy         string
	UpdateTime       *time.Time
	Remark           string
}

type AiModelQuery struct {
	ModelCode string
	ModelName string
	Provider  string
	Status    string
	Scope     string
	PageNum   int
	PageSize  int
}

func (s *Store) ListAiModels(ctx context.Context, q AiModelQuery, page bool) ([]AiModelDetail, int64, error) {
	where, args := []string{"1=1"}, []interface{}{}
	if q.ModelCode != "" {
		where = append(where, "model_code LIKE ?")
		args = append(args, "%"+q.ModelCode+"%")
	}
	if q.ModelName != "" {
		where = append(where, "model_name LIKE ?")
		args = append(args, "%"+q.ModelName+"%")
	}
	if q.Provider != "" {
		where = append(where, "provider = ?")
		args = append(args, q.Provider)
	}
	if q.Status != "" {
		where = append(where, "status = ?")
		args = append(args, q.Status)
	}
	if q.Scope != "" {
		where = append(where, "scope = ?")
		args = append(args, q.Scope)
	}
	clause := strings.Join(where, " AND ")
	var total int64
	if page {
		if err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM ai_models WHERE "+clause, args...).Scan(&total); err != nil {
			return nil, 0, err
		}
	}
	query := `
SELECT model_id, model_code, model_name, provider, model_sort, scope, api_key, base_url,
       model_type, max_tokens, temperature, support_reasoning, support_images, status,
       user_id, dept_id, create_by, create_time, update_by, update_time, remark
FROM ai_models WHERE ` + clause + ` ORDER BY model_sort, model_id`
	if page {
		if q.PageNum < 1 {
			q.PageNum = 1
		}
		if q.PageSize < 1 {
			q.PageSize = 10
		}
		offset := (q.PageNum - 1) * q.PageSize
		query += fmt.Sprintf(" LIMIT %d OFFSET %d", q.PageSize, offset)
	}
	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := make([]AiModelDetail, 0)
	for rows.Next() {
		d, err := scanAiModelRows(rows)
		if err != nil {
			return nil, 0, err
		}
		out = append(out, *d)
	}
	return out, total, rows.Err()
}

func (s *Store) GetAiModel(ctx context.Context, modelID int64) (*AiModelDetail, error) {
	row := s.db.QueryRowContext(ctx, `
SELECT model_id, model_code, model_name, provider, model_sort, scope, api_key, base_url,
       model_type, max_tokens, temperature, support_reasoning, support_images, status,
       user_id, dept_id, create_by, create_time, update_by, update_time, remark
FROM ai_models WHERE model_id = ?`, modelID)
	return scanAiModelRow(row)
}

func (s *Store) InsertAiModel(ctx context.Context, m map[string]interface{}, operator string, userID, deptID int64) error {
	now := timeutil.NowBeijing()
	apiKey := strField(m, "apiKey", "")
	if apiKey != "" && apiKey != maskedAPIKey {
		apiKey = crypto.EncryptCredential(apiKey, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
	}
	_, err := s.db.ExecContext(ctx, `
INSERT INTO ai_models (model_code, model_name, provider, model_sort, scope, api_key, base_url,
  model_type, max_tokens, temperature, support_reasoning, support_images, status,
  user_id, dept_id, create_by, create_time, update_by, update_time, remark)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		strField(m, "modelCode", ""), strField(m, "modelName", ""), strField(m, "provider", "OpenAI"),
		intField(m, "modelSort", 0), strField(m, "scope", "chat"), nullStr(apiKey),
		strField(m, "baseUrl", ""), strField(m, "modelType", ""), intField(m, "maxTokens", 0),
		floatField(m, "temperature", 0.7), strField(m, "supportReasoning", "N"),
		strField(m, "supportImages", "N"), strField(m, "status", "0"),
		userID, deptID, operator, now, operator, now, strField(m, "remark", ""))
	return err
}

func (s *Store) UpdateAiModel(ctx context.Context, m map[string]interface{}, operator string) error {
	modelID := int64(intField(m, "modelId", 0))
	if modelID <= 0 {
		return fmt.Errorf("AI模型不存在")
	}
	existing, err := s.GetAiModel(ctx, modelID)
	if err != nil {
		return err
	}
	if existing == nil || existing.ModelID == 0 {
		return fmt.Errorf("AI模型不存在")
	}
	apiKey := existing.APIKeyEnc
	if v := strField(m, "apiKey", ""); v != "" && v != maskedAPIKey {
		apiKey = crypto.EncryptCredential(v, s.cfg.CredentialEncryptionKey, s.cfg.JWTSecret)
	}
	now := timeutil.NowBeijing()
	_, err = s.db.ExecContext(ctx, `
UPDATE ai_models SET model_code=?, model_name=?, provider=?, model_sort=?, scope=?, api_key=?, base_url=?,
  model_type=?, max_tokens=?, temperature=?, support_reasoning=?, support_images=?, status=?,
  update_by=?, update_time=?, remark=?
WHERE model_id=?`,
		strField(m, "modelCode", existing.ModelCode), strField(m, "modelName", existing.ModelName),
		strField(m, "provider", existing.Provider), intField(m, "modelSort", existing.ModelSort),
		strField(m, "scope", existing.Scope), nullStr(apiKey),
		strField(m, "baseUrl", existing.BaseURL), strField(m, "modelType", existing.ModelType),
		intField(m, "maxTokens", existing.MaxTokens), floatField(m, "temperature", existing.Temperature),
		strField(m, "supportReasoning", existing.SupportReasoning),
		strField(m, "supportImages", existing.SupportImages), strField(m, "status", existing.Status),
		operator, now, strField(m, "remark", existing.Remark), modelID)
	return err
}

func (s *Store) DeleteAiModels(ctx context.Context, ids []int64) error {
	if len(ids) == 0 {
		return fmt.Errorf("传入模型id为空")
	}
	ph := strings.Repeat("?,", len(ids))
	ph = ph[:len(ph)-1]
	args := make([]interface{}, len(ids))
	for i, id := range ids {
		args[i] = id
	}
	_, err := s.db.ExecContext(ctx, "DELETE FROM ai_models WHERE model_id IN ("+ph+")", args...)
	return err
}

func scanAiModelRow(row *sql.Row) (*AiModelDetail, error) {
	d := &AiModelDetail{}
	var modelName, scope, apiKey, baseURL, modelType, remark sql.NullString
	var maxTokens sql.NullInt64
	var temp sql.NullFloat64
	var createTime, updateTime sql.NullTime
	err := row.Scan(&d.ModelID, &d.ModelCode, &modelName, &d.Provider, &d.ModelSort, &scope,
		&apiKey, &baseURL, &modelType, &maxTokens, &temp, &d.SupportReasoning, &d.SupportImages,
		&d.Status, &d.UserID, &d.DeptID, &d.CreateBy, &createTime, &d.UpdateBy, &updateTime, &remark)
	if err != nil {
		return nil, err
	}
	d.ModelName = modelName.String
	d.Scope = scope.String
	d.APIKeyEnc = apiKey.String
	d.BaseURL = baseURL.String
	d.ModelType = modelType.String
	if maxTokens.Valid {
		d.MaxTokens = int(maxTokens.Int64)
	}
	if temp.Valid {
		d.Temperature = temp.Float64
	}
	d.Remark = remark.String
	if createTime.Valid {
		t := createTime.Time
		d.CreateTime = &t
	}
	if updateTime.Valid {
		t := updateTime.Time
		d.UpdateTime = &t
	}
	return d, nil
}

func scanAiModelRows(rows *sql.Rows) (*AiModelDetail, error) {
	d := &AiModelDetail{}
	var modelName, scope, apiKey, baseURL, modelType, remark sql.NullString
	var maxTokens sql.NullInt64
	var temp sql.NullFloat64
	var createTime, updateTime sql.NullTime
	err := rows.Scan(&d.ModelID, &d.ModelCode, &modelName, &d.Provider, &d.ModelSort, &scope,
		&apiKey, &baseURL, &modelType, &maxTokens, &temp, &d.SupportReasoning, &d.SupportImages,
		&d.Status, &d.UserID, &d.DeptID, &d.CreateBy, &createTime, &d.UpdateBy, &updateTime, &remark)
	if err != nil {
		return nil, err
	}
	d.ModelName = modelName.String
	d.Scope = scope.String
	d.APIKeyEnc = apiKey.String
	d.BaseURL = baseURL.String
	d.ModelType = modelType.String
	if maxTokens.Valid {
		d.MaxTokens = int(maxTokens.Int64)
	}
	if temp.Valid {
		d.Temperature = temp.Float64
	}
	d.Remark = remark.String
	if createTime.Valid {
		t := createTime.Time
		d.CreateTime = &t
	}
	if updateTime.Valid {
		t := updateTime.Time
		d.UpdateTime = &t
	}
	return d, nil
}

func FormatAiModel(d AiModelDetail, maskKey bool) map[string]interface{} {
	out := map[string]interface{}{
		"modelId": d.ModelID, "modelCode": d.ModelCode, "modelName": d.ModelName,
		"provider": d.Provider, "modelSort": d.ModelSort, "scope": d.Scope,
		"baseUrl": d.BaseURL, "modelType": d.ModelType, "maxTokens": d.MaxTokens,
		"temperature": d.Temperature, "supportReasoning": d.SupportReasoning,
		"supportImages": d.SupportImages, "status": d.Status, "remark": d.Remark,
	}
	if maskKey {
		out["apiKey"] = maskedAPIKey
	} else if d.APIKey != "" {
		out["apiKey"] = d.APIKey
	} else {
		out["apiKey"] = maskedAPIKey
	}
	if d.UserID.Valid {
		out["userId"] = d.UserID.Int64
	}
	if d.DeptID.Valid {
		out["deptId"] = d.DeptID.Int64
	}
	if d.CreateBy != "" {
		out["createBy"] = d.CreateBy
	}
	if d.UpdateBy != "" {
		out["updateBy"] = d.UpdateBy
	}
	if d.CreateTime != nil {
		out["createTime"] = timeutil.FormatBeijing(*d.CreateTime)
	}
	if d.UpdateTime != nil {
		out["updateTime"] = timeutil.FormatBeijing(*d.UpdateTime)
	}
	return out
}

func floatField(m map[string]interface{}, key string, fallback float64) float64 {
	switch v := m[key].(type) {
	case float64:
		return v
	case int:
		return float64(v)
	default:
		return fallback
	}
}
