package llm

import (
	"context"
	"sync"
)

// RunRegistry tracks in-flight chat runs for cancellation.
type RunRegistry struct {
	mu   sync.Mutex
	runs map[string]context.CancelFunc
}

func NewRunRegistry() *RunRegistry {
	return &RunRegistry{runs: make(map[string]context.CancelFunc)}
}

func (r *RunRegistry) Register(runID string, cancel context.CancelFunc) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if prev, ok := r.runs[runID]; ok {
		prev()
	}
	r.runs[runID] = cancel
}

func (r *RunRegistry) Cancel(runID string) bool {
	r.mu.Lock()
	cancel, ok := r.runs[runID]
	if ok {
		delete(r.runs, runID)
	}
	r.mu.Unlock()
	if ok {
		cancel()
	}
	return ok
}

func (r *RunRegistry) Done(runID string) {
	r.mu.Lock()
	delete(r.runs, runID)
	r.mu.Unlock()
}
