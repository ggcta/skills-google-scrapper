package cli

import (
	"context"
	"os"
	"os/signal"
	"syscall"
)

// browserSignalContext returns a context canceled on SIGINT or SIGTERM. Every
// command that drives a browser derives its session from this context so Chrome
// is always torn down gracefully when the process is interrupted or terminated:
// chromedp kills the Chrome process when this parent context is canceled, and
// the command's deferred sess.Close() runs on return. This is backlog #1 — never
// leave an orphaned browser (which would keep the profile locked).
func browserSignalContext() (context.Context, context.CancelFunc) {
	return signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
}
