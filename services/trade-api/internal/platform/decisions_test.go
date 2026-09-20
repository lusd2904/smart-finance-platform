package platform

import (
	"reflect"
	"testing"
)

func TestListAutoDecisionsTakesUserID(t *testing.T) {
	typ := reflect.TypeOf((*Repo).ListAutoDecisions)
	if typ.NumIn() != 5 {
		t.Fatalf("want (Repo, ctx, userID, limit, cycleID), got %d", typ.NumIn())
	}
	if typ.In(2).Kind() != reflect.Int {
		t.Fatalf("userID arg %v", typ.In(2))
	}
	svc := reflect.TypeOf((*Service).ListAutoDecisions)
	if svc.NumIn() != 5 || svc.In(2).Kind() != reflect.Int {
		t.Fatalf("service userID arg %v in=%d", svc.In(2), svc.NumIn())
	}
}
