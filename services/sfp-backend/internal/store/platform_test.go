package store

import (
	"strings"
	"testing"
)

func TestIsAnalysisTargetGoKeys(t *testing.T) {
	for key := range analysisGoInvokeTargets {
		if !IsAnalysisTarget(key) {
			t.Fatalf("expected analysis target for %s", key)
		}
	}
	if IsAnalysisTarget("module_task.scheduler_test.job") {
		t.Fatal("scheduler_test should not be analysis target")
	}
}

func TestCategoryFromTargetGoKeys(t *testing.T) {
	if CategoryFromTarget("finance_briefings") != "market" {
		t.Fatalf("finance_briefings category")
	}
	if CategoryFromTarget("indicator_refresh") != "quant" {
		t.Fatalf("indicator_refresh category")
	}
	if CategoryFromTarget("feishu_push") != "trade" {
		t.Fatalf("feishu_push category")
	}
	if CategoryFromTarget("module_task.quant_task.run_indicator_refresh_job") != "quant" {
		t.Fatalf("python path category")
	}
}

func TestGoInvokeTargetSQLIn(t *testing.T) {
	sql := goInvokeTargetSQLIn()
	for _, key := range []string{"'finance_briefings'", "'indicator_refresh'", "'feishu_push'"} {
		if !strings.Contains(sql, key) {
			t.Fatalf("sql in list missing %s: %s", key, sql)
		}
	}
}
