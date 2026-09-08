package tradeexec

import (
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/longbridge/openapi-go/quote"
)

// Quote WS invariant (process-wide):
//
//   - At most one live Longbridge QuoteContext per credential signature.
//   - Concurrent acquires singleflight the same Dial; they never spawn extra reconnecters.
//   - Failed Dials use exponential backoff + jitter; repeated EOF trips a circuit
//     so quote.NewFromCfg is not called in a tight loop.
//   - Request handlers must not Close the shared session. Close only happens when
//     credentials rotate (old conn) or the process shuts down (CloseQuoteSessions).
//
// Why this exists: quote.NewFromCfg dials a websocket whose protocol client
// reconnects forever (MaxReconnect=0, 1s sleep, reconnect loop ignores Close).
// Opening a context per HTTP request leaked reconnect goroutines and grew RSS
// toward the slim 320MiB mem_limit.

const (
	quoteMinBackoff  = 500 * time.Millisecond
	quoteMaxBackoff  = 30 * time.Second
	quoteMaxFails    = 5
	quoteCircuitHold = 60 * time.Second
)

var (
	errQuoteCooling = errors.New("longbridge quote websocket cooling down")
	errQuoteCircuit = errors.New("longbridge quote websocket circuit open")
)

// quoteSession is the Close surface of a Longbridge QuoteContext (or a test fake).
type quoteSession interface {
	Close() error
}

type quoteFactory func(Creds) (quoteSession, error)

type quoteCreate struct {
	done chan struct{}
	sess quoteSession
	err  error
}

type quoteEntry struct {
	sess     quoteSession
	failures int
	nextTry  time.Time
	create   *quoteCreate
}

type quotePool struct {
	mu          sync.Mutex
	entries     map[string]*quoteEntry
	factory     quoteFactory
	now         func() time.Time
	jitter      func(time.Duration) time.Duration
	minBackoff  time.Duration
	maxBackoff  time.Duration
	maxFails    int
	circuitHold time.Duration
}

func newQuotePool(factory quoteFactory) *quotePool {
	p := &quotePool{
		entries:     make(map[string]*quoteEntry),
		factory:     factory,
		now:         time.Now,
		minBackoff:  quoteMinBackoff,
		maxBackoff:  quoteMaxBackoff,
		maxFails:    quoteMaxFails,
		circuitHold: quoteCircuitHold,
	}
	p.jitter = p.defaultJitter
	return p
}

func newSDKQuoteSession(creds Creds) (quoteSession, error) {
	cfg, err := buildConfig(creds)
	if err != nil {
		return nil, err
	}
	return quote.NewFromCfg(cfg)
}

var sharedQuotes = newQuotePool(newSDKQuoteSession)

// CloseQuoteSessions closes every cached Longbridge QuoteContext.
// Call on process shutdown. Request handlers must not Close the shared session.
func CloseQuoteSessions() {
	sharedQuotes.CloseAll()
}

func (p *quotePool) CloseAll() {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, e := range p.entries {
		if e == nil || e.sess == nil {
			continue
		}
		old := e.sess
		e.sess = nil
		_ = old.Close()
	}
}

func (p *quotePool) acquire(creds Creds) (quoteSession, error) {
	key := creds.Signature()
	p.mu.Lock()
	e := p.entries[key]
	if e == nil {
		e = &quoteEntry{}
		p.entries[key] = e
	}
	p.evictStaleLocked(creds.UserID, key)

	if e.sess != nil {
		sess := e.sess
		p.mu.Unlock()
		return sess, nil
	}

	now := p.now()
	if !e.nextTry.IsZero() && now.Before(e.nextTry) {
		wait := e.nextTry.Sub(now)
		err := errQuoteCooling
		if e.failures >= p.maxFails {
			err = errQuoteCircuit
		}
		p.mu.Unlock()
		return nil, fmt.Errorf("%w: retry in %s", err, wait.Round(time.Millisecond))
	}

	if e.create != nil {
		call := e.create
		p.mu.Unlock()
		<-call.done
		return call.sess, call.err
	}

	call := &quoteCreate{done: make(chan struct{})}
	e.create = call
	p.mu.Unlock()

	sess, err := p.factory(creds)

	p.mu.Lock()
	e.create = nil
	if err != nil {
		e.failures++
		if e.failures >= p.maxFails {
			e.nextTry = p.now().Add(p.circuitHold)
		} else {
			e.nextTry = p.now().Add(p.backoff(e.failures))
		}
		call.err = err
		close(call.done)
		p.mu.Unlock()
		return nil, err
	}
	e.sess = sess
	e.failures = 0
	e.nextTry = time.Time{}
	call.sess = sess
	close(call.done)
	p.mu.Unlock()
	return sess, nil
}

func (p *quotePool) evictStaleLocked(userID int, keepKey string) {
	if userID <= 0 {
		return
	}
	prefix := itoa(userID) + ":"
	for k, e := range p.entries {
		if k == keepKey || e == nil || e.sess == nil {
			continue
		}
		if strings.HasPrefix(k, prefix) {
			old := e.sess
			e.sess = nil
			go func(s quoteSession) { _ = s.Close() }(old)
		}
	}
}

func (p *quotePool) backoff(failures int) time.Duration {
	if failures < 1 {
		failures = 1
	}
	d := p.minBackoff
	for i := 1; i < failures && d < p.maxBackoff; i++ {
		d *= 2
	}
	if d > p.maxBackoff {
		d = p.maxBackoff
	}
	return p.jitter(d)
}

func (p *quotePool) defaultJitter(d time.Duration) time.Duration {
	if d <= 0 {
		return d
	}
	// ±20% so concurrent processes do not retry in lockstep.
	span := int64(d / 5)
	if span <= 0 {
		return d
	}
	delta := time.Duration(p.now().UnixNano() % (span*2 + 1))
	return d - time.Duration(span) + delta
}

func quoteCtx(creds Creds) (*quote.QuoteContext, error) {
	sess, err := sharedQuotes.acquire(creds)
	if err != nil {
		return nil, err
	}
	qctx, ok := sess.(*quote.QuoteContext)
	if !ok {
		return nil, errors.New("longbridge quote session type mismatch")
	}
	return qctx, nil
}
