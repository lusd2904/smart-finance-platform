package analysis

import (
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/store"
)

func TestCatalogInvokeTargetsAreGoKeys(t *testing.T) {
	seen := map[int]bool{}
	for _, spec := range Catalog {
		if seen[spec.JobID] {
			t.Fatalf("duplicate job id %d", spec.JobID)
		}
		seen[spec.JobID] = true
		if spec.InvokeTarget != spec.QueueType {
			t.Fatalf("job %d invoke=%s queueType=%s", spec.JobID, spec.InvokeTarget, spec.QueueType)
		}
		if !store.IsAnalysisTarget(spec.InvokeTarget) {
			t.Fatalf("job %d invoke %s is not an analysis target", spec.JobID, spec.InvokeTarget)
		}
		if got := store.CategoryFromTarget(spec.InvokeTarget); got != spec.Category {
			t.Fatalf("job %d category catalog=%s store=%s", spec.JobID, spec.Category, got)
		}
	}
}
