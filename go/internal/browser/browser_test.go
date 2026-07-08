package browser

import (
	"context"
	"net"
	"testing"
	"time"
)

// TestNavigateTimeout proves a page that never responds can't hang the run
// forever: Navigate must return an error within roughly NavTimeout, and the
// session must survive (a timeout is not a crash).
func TestNavigateTimeout(t *testing.T) {
	// A listener that accepts connections but never sends a response, so the
	// browser stalls waiting for the page to load.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			_ = c // hold the connection open, never respond
		}
	}()

	defer swapNavTimeout(4 * time.Second)()

	sess, err := Launch(context.Background(), Options{Headless: true})
	if err != nil {
		t.Skipf("chrome unavailable: %v", err)
	}
	defer sess.Close()

	start := time.Now()
	_, _, err = sess.Navigate("http://"+ln.Addr().String(), 50*time.Millisecond)
	elapsed := time.Since(start)

	if err == nil {
		t.Error("expected a timeout error from a non-responding server")
	}
	if elapsed > 15*time.Second {
		t.Errorf("Navigate did not respect the timeout: took %v", elapsed)
	}
	if !sess.alive() {
		t.Error("session should stay alive after a navigation timeout")
	}
}

// TestNavigateRecoversDeadSession proves that if the browser context has died,
// the next Navigate transparently relaunches and succeeds.
func TestNavigateRecoversDeadSession(t *testing.T) {
	sess, err := Launch(context.Background(), Options{Headless: true})
	if err != nil {
		t.Skipf("chrome unavailable: %v", err)
	}
	defer sess.Close()

	// Simulate a crash: tear the session's context down.
	sess.Close()
	if sess.alive() {
		t.Fatal("precondition: session should be dead after Close")
	}

	// Navigate should relaunch and succeed against a trivial page.
	if _, _, err := sess.Navigate("about:blank", 50*time.Millisecond); err != nil {
		t.Errorf("expected relaunch + success, got %v", err)
	}
	if !sess.alive() {
		t.Error("session should be alive again after recovery")
	}
}

// swapNavTimeout sets NavTimeout to d and returns a restore func.
func swapNavTimeout(d time.Duration) func() {
	old := NavTimeout
	NavTimeout = d
	return func() { NavTimeout = old }
}
