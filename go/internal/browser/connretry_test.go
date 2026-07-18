package browser

import (
	"errors"
	"testing"
	"time"
)

// TestIsConnErr proves the net-stack connectivity codes are recognized while
// page/app errors and nil are not.
func TestIsConnErr(t *testing.T) {
	conn := []error{
		errors.New("page load error net::ERR_CONNECTION_TIMED_OUT"),
		errors.New("page load error net::ERR_QUIC_PROTOCOL_ERROR"),
		errors.New("net::ERR_INTERNET_DISCONNECTED"),
		errors.New("net::ERR_NAME_NOT_RESOLVED"),
	}
	for _, e := range conn {
		if !isConnErr(e) {
			t.Errorf("isConnErr(%v) = false, want true", e)
		}
	}
	notConn := []error{
		nil,
		errors.New("ql-contents-menu or ql-course-outline not found"),
		errors.New("context deadline exceeded"),
		errors.New("net::ERR_ABORTED"), // navigation aborted is not a connectivity loss
	}
	for _, e := range notConn {
		if isConnErr(e) {
			t.Errorf("isConnErr(%v) = true, want false", e)
		}
	}
}

// TestWithConnRetryRecovers proves a connection that comes back within the budget
// lets the navigation succeed, and the session is not marked connection-lost.
func TestWithConnRetryRecovers(t *testing.T) {
	defer swapConnRetry(1*time.Second, 5*time.Millisecond)()
	s := &Session{}
	calls := 0
	err := s.withConnRetry(func() error {
		calls++
		if calls < 3 {
			return errors.New("page load error net::ERR_CONNECTION_TIMED_OUT")
		}
		return nil
	})
	if err != nil {
		t.Fatalf("withConnRetry = %v, want nil after recovery", err)
	}
	if calls != 3 {
		t.Errorf("attempts = %d, want 3", calls)
	}
	if s.ConnectionLost() {
		t.Error("session must not be marked connection-lost after a recovery")
	}
}

// TestWithConnRetryExhausts proves that when the connection stays down past the
// budget, withConnRetry gives up with ErrConnectionLost, marks the session, and
// thereafter fails fast without retrying again.
func TestWithConnRetryExhausts(t *testing.T) {
	defer swapConnRetry(40*time.Millisecond, 10*time.Millisecond)()
	s := &Session{}
	connErr := func() error { return errors.New("net::ERR_INTERNET_DISCONNECTED") }

	err := s.withConnRetry(connErr)
	if !errors.Is(err, ErrConnectionLost) {
		t.Fatalf("withConnRetry = %v, want ErrConnectionLost", err)
	}
	if !s.ConnectionLost() {
		t.Error("session should be marked connection-lost after the budget is spent")
	}

	// A subsequent navigation must short-circuit: no further waiting/retrying.
	calls := 0
	start := time.Now()
	err = s.withConnRetry(func() error { calls++; return nil })
	if !errors.Is(err, ErrConnectionLost) {
		t.Errorf("post-loss withConnRetry = %v, want ErrConnectionLost", err)
	}
	if calls != 0 {
		t.Errorf("post-loss attempts = %d, want 0 (fail fast)", calls)
	}
	if time.Since(start) > 20*time.Millisecond {
		t.Error("post-loss withConnRetry should return immediately, not wait")
	}
}

// TestWithConnRetryPassesThroughOtherErrors proves a non-connectivity error is
// returned at once, without retrying and without marking the session lost.
func TestWithConnRetryPassesThroughOtherErrors(t *testing.T) {
	defer swapConnRetry(1*time.Second, 5*time.Millisecond)()
	s := &Session{}
	want := errors.New("outline: ql-course-outline not found")
	calls := 0
	err := s.withConnRetry(func() error { calls++; return want })
	if err != want {
		t.Fatalf("withConnRetry = %v, want the page error passed through", err)
	}
	if calls != 1 {
		t.Errorf("attempts = %d, want 1 (no retry for a page error)", calls)
	}
	if s.ConnectionLost() {
		t.Error("a page error must not mark the session connection-lost")
	}
}

// swapConnRetry sets the connection-retry budget/interval and returns a restore
// func, so tests run fast.
func swapConnRetry(budget, interval time.Duration) func() {
	oldB, oldI := ConnRetryBudget, connRetryInterval
	ConnRetryBudget, connRetryInterval = budget, interval
	return func() { ConnRetryBudget, connRetryInterval = oldB, oldI }
}
