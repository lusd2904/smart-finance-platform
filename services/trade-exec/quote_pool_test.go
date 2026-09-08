package tradeexec

import (
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

type fakeQuoteConn struct {
	id     int
	closed atomic.Int32
}

func (f *fakeQuoteConn) Close() error {
	f.closed.Add(1)
	return nil
}

func testCreds(token string) Creds {
	return Creds{UserID: 1, AppKey: "k", AppSecret: "s", AccessToken: token, Region: "cn"}
}

func testPool(factory quoteFactory) *quotePool {
	p := newQuotePool(factory)
	p.jitter = func(d time.Duration) time.Duration { return d }
	p.now = func() time.Time { return time.Unix(1_700_000_000, 0) }
	p.minBackoff = time.Second
	p.maxBackoff = 8 * time.Second
	p.maxFails = 3
	p.circuitHold = time.Minute
	return p
}

func TestQuotePoolSharesOneConn(t *testing.T) {
	var n atomic.Int32
	p := testPool(func(Creds) (quoteSession, error) {
		id := int(n.Add(1))
		return &fakeQuoteConn{id: id}, nil
	})
	creds := testCreds("t")

	const workers = 32
	got := make([]quoteSession, workers)
	var wg sync.WaitGroup
	errCh := make(chan error, workers)
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			s, err := p.acquire(creds)
			if err != nil {
				errCh <- err
				return
			}
			got[i] = s
		}(i)
	}
	wg.Wait()
	close(errCh)
	for err := range errCh {
		t.Fatalf("acquire: %v", err)
	}
	if n.Load() != 1 {
		t.Fatalf("factory called %d times, want 1 (singleflight + share)", n.Load())
	}
	first := got[0]
	for i, s := range got {
		if s != first {
			t.Fatalf("worker %d got a different session", i)
		}
	}
}

func TestQuotePoolSingleflightWhileCreateBlocks(t *testing.T) {
	started := make(chan struct{})
	release := make(chan struct{})
	var n atomic.Int32
	var once sync.Once
	p := testPool(func(Creds) (quoteSession, error) {
		n.Add(1)
		once.Do(func() { close(started) })
		<-release
		return &fakeQuoteConn{id: 1}, nil
	})

	const workers = 10
	var wg sync.WaitGroup
	errCh := make(chan error, workers)
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := p.acquire(testCreds("t")); err != nil {
				errCh <- err
			}
		}()
	}
	<-started
	if n.Load() != 1 {
		t.Fatalf("factory started %d times while first Dial still in flight", n.Load())
	}
	close(release)
	wg.Wait()
	close(errCh)
	for err := range errCh {
		t.Fatalf("acquire: %v", err)
	}
	if n.Load() != 1 {
		t.Fatalf("factory called %d times, want 1", n.Load())
	}
}

func TestQuotePoolBackoffAfterCreateFailure(t *testing.T) {
	var n atomic.Int32
	now := time.Unix(1_700_000_000, 0)
	p := testPool(func(Creds) (quoteSession, error) {
		n.Add(1)
		return nil, errors.New("websocket: close 1006 (abnormal closure): unexpected EOF")
	})
	p.now = func() time.Time { return now }

	if _, err := p.acquire(testCreds("t")); err == nil {
		t.Fatal("expected first acquire to fail")
	}
	if n.Load() != 1 {
		t.Fatalf("factory=%d", n.Load())
	}
	if _, err := p.acquire(testCreds("t")); !errors.Is(err, errQuoteCooling) {
		t.Fatalf("want cooling error, got %v", err)
	}
	if n.Load() != 1 {
		t.Fatalf("immediate retry must not Dial again, factory=%d", n.Load())
	}

	now = now.Add(time.Second)
	if _, err := p.acquire(testCreds("t")); err == nil {
		t.Fatal("expected second acquire to fail")
	}
	if n.Load() != 2 {
		t.Fatalf("after backoff factory=%d want 2", n.Load())
	}
}

func TestQuotePoolCircuitOpenAfterRepeatedEOF(t *testing.T) {
	var n atomic.Int32
	now := time.Unix(1_700_000_000, 0)
	p := testPool(func(Creds) (quoteSession, error) {
		n.Add(1)
		return nil, errors.New("unexpected EOF")
	})
	p.now = func() time.Time { return now }

	for i := 0; i < 1000; i++ {
		_, _ = p.acquire(testCreds("t"))
		if n.Load() < int32(p.maxFails) {
			now = now.Add(p.backoff(int(n.Load())))
		}
	}
	if n.Load() != 3 {
		t.Fatalf("unbounded reconnecters: factory called %d times, want %d (circuit)", n.Load(), p.maxFails)
	}
	if _, err := p.acquire(testCreds("t")); !errors.Is(err, errQuoteCircuit) {
		t.Fatalf("want circuit open, got %v", err)
	}

	now = now.Add(p.circuitHold)
	_, _ = p.acquire(testCreds("t"))
	if n.Load() != 4 {
		t.Fatalf("half-open probe factory=%d want 4", n.Load())
	}
}

func TestQuotePoolClosesOldConnOnCredentialRotate(t *testing.T) {
	var n atomic.Int32
	p := testPool(func(creds Creds) (quoteSession, error) {
		id := int(n.Add(1))
		return &fakeQuoteConn{id: id}, nil
	})

	first, err := p.acquire(testCreds("old"))
	if err != nil {
		t.Fatal(err)
	}
	old := first.(*fakeQuoteConn)

	second, err := p.acquire(testCreds("new"))
	if err != nil {
		t.Fatal(err)
	}
	if second == first {
		t.Fatal("rotated credentials must open a new session")
	}
	deadline := time.Now().Add(2 * time.Second)
	for old.closed.Load() == 0 && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if old.closed.Load() == 0 {
		t.Fatal("old QuoteContext was not Closed after credential rotate")
	}
	if n.Load() != 2 {
		t.Fatalf("factory=%d want 2", n.Load())
	}
}

func TestQuotePoolCloseAllClosesLiveConn(t *testing.T) {
	sess := &fakeQuoteConn{id: 1}
	p := testPool(func(Creds) (quoteSession, error) { return sess, nil })
	if _, err := p.acquire(testCreds("t")); err != nil {
		t.Fatal(err)
	}
	p.CloseAll()
	if sess.closed.Load() != 1 {
		t.Fatalf("CloseAll closed=%d want 1", sess.closed.Load())
	}
}

func TestQuoteBackoffSchedule(t *testing.T) {
	p := testPool(func(Creds) (quoteSession, error) { return &fakeQuoteConn{}, nil })
	if got := p.backoff(1); got != time.Second {
		t.Fatalf("backoff(1)=%s want 1s", got)
	}
	if got := p.backoff(2); got != 2*time.Second {
		t.Fatalf("backoff(2)=%s want 2s", got)
	}
	if got := p.backoff(3); got != 4*time.Second {
		t.Fatalf("backoff(3)=%s want 4s", got)
	}
	if got := p.backoff(10); got != 8*time.Second {
		t.Fatalf("backoff(10)=%s want cap 8s", got)
	}
}
