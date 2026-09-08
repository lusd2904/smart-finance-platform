package platform

import (
	"fmt"
	"strings"
	"time"
)

var statusLabels = map[string]string{
	"pending_review": "待复核",
	"confirmed":      "已确认",
	"ignored":        "已忽略",
	"need_review":    "需复核",
	"overdue":        "超期",
}

var allowedTransitions = map[string]map[string]bool{
	"pending_review": {"confirmed": true, "ignored": true, "need_review": true, "overdue": true},
	"need_review":    {"confirmed": true, "ignored": true, "overdue": true, "pending_review": true},
	"overdue":        {"confirmed": true, "ignored": true, "need_review": true},
	"confirmed":      {"need_review": true},
	"ignored":        {"need_review": true},
}

var terminalStatuses = map[string]bool{"confirmed": true, "ignored": true}
var openStatuses = map[string]bool{"pending_review": true, "need_review": true}
var remarkRequired = map[string]bool{"confirmed": true, "ignored": true, "need_review": true}

func normalizeStatus(raw, handled string) string {
	value := strings.TrimSpace(raw)
	if statusLabels[value] != "" {
		return value
	}
	if handled == "1" {
		return "confirmed"
	}
	return "pending_review"
}

func effectiveStatus(stored, handled string, createTime time.Time, now time.Time) string {
	status := normalizeStatus(stored, handled)
	if terminalStatuses[status] || status == "overdue" {
		return status
	}
	if openStatuses[status] && !createTime.IsZero() {
		if now.Sub(createTime) >= 24*time.Hour {
			return "overdue"
		}
	}
	return status
}

func handledFlag(status string) string {
	if terminalStatuses[normalizeStatus(status, "")] {
		return "1"
	}
	return "0"
}

func canTransition(source, target string) bool {
	m, ok := allowedTransitions[source]
	if !ok {
		return false
	}
	return m[target]
}

type StatusChange struct {
	ReviewStatus string
	Handled      string
	HandleRemark string
	HandledBy    string
	HandleTime   time.Time
}

func applyStatusChange(current, target, remark, operator string, now time.Time) (StatusChange, error) {
	source := normalizeStatus(current, "")
	dest := normalizeStatus(target, "")
	if statusLabels[dest] == "" {
		return StatusChange{}, fmt.Errorf("不支持的风控状态: %s", target)
	}
	if source == dest {
		return StatusChange{}, fmt.Errorf("状态未变化")
	}
	if !canTransition(source, dest) {
		return StatusChange{}, fmt.Errorf("不允许从%s变更为%s", statusLabels[source], statusLabels[dest])
	}
	note := strings.TrimSpace(remark)
	if remarkRequired[dest] && note == "" {
		return StatusChange{}, fmt.Errorf("请填写处理备注")
	}
	return StatusChange{
		ReviewStatus: dest,
		Handled:      handledFlag(dest),
		HandleRemark: note,
		HandledBy:    operator,
		HandleTime:   now,
	}, nil
}

func statusLabel(code string) string {
	if l, ok := statusLabels[code]; ok {
		return l
	}
	return code
}
