package jobs

import "testing"

func TestExtractRequirementPayload(t *testing.T) {
	text := `好的，整理如下 {"action":"upsert_requirements","items":[{"title":"登录页改版","detail":"统一暗色主题","priority":"P1"}]}`
	items := extractRequirementPayload(text)
	if len(items) != 1 {
		t.Fatalf("expected 1 item, got %d", len(items))
	}
	if items[0]["title"] != "登录页改版" {
		t.Fatalf("unexpected title: %s", items[0]["title"])
	}
	if extractRequirementPayload("这个需求范围太大") != nil {
		t.Fatalf("expected nil for non-json reply")
	}
}

func TestIsConfirmText(t *testing.T) {
	if !isConfirmText("确定") {
		t.Fatalf("exact confirm should match")
	}
	if !isConfirmText("请总结并写入清单") {
		t.Fatalf("regex confirm should match")
	}
	if isConfirmText("还在讨论") {
		t.Fatalf("non-confirm should not match")
	}
}

func TestInferReqRound(t *testing.T) {
	history := []reqMessage{
		{Role: "user"}, {Role: "ai"}, {Role: "user"}, {Role: "ai"},
	}
	if inferReqRound(history) != 3 {
		t.Fatalf("expected round 3, got %d", inferReqRound(history))
	}
}
