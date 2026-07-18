// Package browser launches Chrome via chromedp, mirroring the Python
// launch_browser: it reuses the same persistent profile folder (so a sign-in
// done from either the Python or Go tool carries over) and applies the same
// anti-automation flags. Headless uses the less-detectable "new" mode.
package browser

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"csb/internal/config"
	"csb/internal/logx"
	"github.com/chromedp/chromedp"
)

// shutdownGrace bounds the graceful browser close so a wedged Chrome can't hang
// the process; after it, the hard allocator cancel takes over.
const shutdownGrace = 5 * time.Second

// ProfileDirName is the default reusable profile folder (matches the Python
// WEBDRIVER_PROFILE_FOLDER_NAME), resolved under the current working directory.
const ProfileDirName = ".webdriver_profiles"

// Options configure a browser launch.
type Options struct {
	// ProfileDir is the user-data-dir. Empty means a throwaway profile.
	ProfileDir string
	// Headless runs Chrome with --headless=new when true.
	Headless bool
	// RemoteWS, when set, connects to an already-running Chrome at this DevTools
	// websocket URL instead of launching a new one (backlog #13). Such a session
	// is "borrowed": Close detaches without terminating that shared browser.
	RemoteWS string
	// DebugPort, when > 0, launches Chrome with a fixed --remote-debugging-port so
	// other processes can later reuse it via RemoteWS.
	DebugPort int
}

// NavTimeout bounds a single navigation/evaluation so a page that hangs (e.g. a
// body that never becomes ready) can't block the whole run forever. It is a var
// so tests can shorten it.
var NavTimeout = 45 * time.Second

// ErrConnectionLost is returned by a navigation once the internet connection has
// been down continuously for longer than ConnRetryBudget. It marks the session
// connection-lost (see ConnectionLost) so the fetch loops stop cleanly — saving
// the items already completed — instead of churning through the remaining items
// against a dead connection.
var ErrConnectionLost = errors.New("internet connection lost")

// ConnRetryBudget bounds how long a navigation keeps retrying while the internet
// connection is down before the run gives up. The user asked for a period of
// time (not a fixed count), so a wall-clock budget is used. A var so tests can
// shorten it.
var ConnRetryBudget = 3 * time.Minute

// connRetryInterval is the wait between connection-retry attempts. A short, fixed
// interval keeps the run responsive to the connection coming back (over the
// 3-minute budget that is ~36 attempts).
var connRetryInterval = 5 * time.Second

// connErrCodes are the Chrome/CDP net-stack error tokens that indicate a lost or
// broken *internet connection* (as opposed to a page- or app-level failure), so a
// navigation that hits one is worth retrying once connectivity returns. chromedp
// surfaces these as "page load error net::ERR_…".
var connErrCodes = []string{
	"ERR_INTERNET_DISCONNECTED",
	"ERR_NETWORK_CHANGED",
	"ERR_CONNECTION_TIMED_OUT",
	"ERR_CONNECTION_RESET",
	"ERR_CONNECTION_CLOSED",
	"ERR_CONNECTION_REFUSED",
	"ERR_CONNECTION_ABORTED",
	"ERR_CONNECTION_FAILED",
	"ERR_NAME_NOT_RESOLVED",
	"ERR_NAME_RESOLUTION_FAILED",
	"ERR_ADDRESS_UNREACHABLE",
	"ERR_PROXY_CONNECTION_FAILED",
	"ERR_QUIC_PROTOCOL_ERROR",
	"ERR_SOCKET_NOT_CONNECTED",
	"ERR_TIMED_OUT",
}

// isConnErr reports whether err looks like a transient internet-connectivity
// failure (one of connErrCodes) rather than a page- or app-level error.
func isConnErr(err error) bool {
	if err == nil {
		return false
	}
	msg := err.Error()
	for _, code := range connErrCodes {
		if strings.Contains(msg, code) {
			return true
		}
	}
	return false
}

// Session is a running browser. Call Close when done. It is self-healing: if the
// underlying browser/tab dies (its context is canceled), the next navigation
// transparently relaunches it, reusing the same on-disk profile so the sign-in
// carries over.
type Session struct {
	Ctx context.Context
	// interrupt is canceled on Ctrl+C / SIGTERM (or a GUI teardown). It drives
	// Interrupted() and triggers a GRACEFUL close — it is deliberately NOT the
	// allocator parent, so a signal never hard-kills Chrome.
	interrupt context.Context
	opts      Options
	mu        sync.Mutex
	cancel    []func()
	// borrowed is true when this session connected to an already-running Chrome
	// (opts.RemoteWS): Close must NOT terminate that shared browser, and a lost
	// connection must NOT spawn a colliding replacement.
	borrowed bool
	// connLost is set once a navigation gave up after the internet connection
	// stayed down past ConnRetryBudget. It drives ConnectionLost(), which the
	// fetch loops check to stop the run cleanly. Guarded by mu.
	connLost bool
}

// Close shuts the browser down gracefully and tears down the allocator. It first
// asks Chrome to close via CDP (chromedp.Cancel → Browser.close) and waits, so
// the profile records a clean exit (no "Chrome didn't shut down correctly") and
// the SingletonLock is released properly; a wedged Chrome falls back to the hard
// allocator cancel after shutdownGrace. Idempotent and safe from any goroutine.
func (s *Session) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cancel == nil {
		return
	}
	// A borrowed session (backlog #13) connected to a browser it does not own, so
	// it must only detach (cancel the local contexts below) — never chromedp.Cancel,
	// which sends Browser.close and would kill the shared Chrome.
	if !s.borrowed && s.Ctx != nil && s.Ctx.Err() == nil {
		done := make(chan struct{})
		go func() {
			defer close(done)
			_ = chromedp.Cancel(s.Ctx) // graceful: Browser.close + wait
		}()
		select {
		case <-done:
		case <-time.After(shutdownGrace):
		}
	}
	for i := len(s.cancel) - 1; i >= 0; i-- {
		s.cancel[i]()
	}
	s.cancel = nil
}

// start launches a fresh browser and wires up s.Ctx / s.cancel. The allocator is
// rooted at Background (not the interrupt context) so a termination signal is
// handled by a graceful Close rather than a hard process kill.
func (s *Session) start() error {
	var allocCtx context.Context
	var cancelAlloc context.CancelFunc
	if s.opts.RemoteWS != "" {
		// Reuse an already-running Chrome (backlog #13). NewRemoteAllocator resolves
		// the browser websocket from the /json/version endpoint when the URL lacks
		// the /devtools/browser/ path.
		allocCtx, cancelAlloc = chromedp.NewRemoteAllocator(context.Background(), s.opts.RemoteWS)
		s.borrowed = true
	} else {
		allocCtx, cancelAlloc = chromedp.NewExecAllocator(context.Background(), allocFlags(s.opts)...)
	}
	ctx, cancelCtx := chromedp.NewContext(allocCtx, chromedp.WithErrorf(quietErrorf))
	// Force the browser to actually start/connect so profile/allocator errors
	// surface here rather than on first navigate.
	if err := chromedp.Run(ctx); err != nil {
		cancelCtx()
		cancelAlloc()
		return err
	}
	s.Ctx = ctx
	s.cancel = []func(){cancelCtx, cancelAlloc}
	return nil
}

// relaunch tears down the (dead) browser and starts a new one. It waits for the
// old browser to release the profile before relaunching, so the new Chrome
// doesn't race the stale lock (which surfaces as Chrome's "Something went wrong
// when opening your profile" dialog).
func (s *Session) relaunch() error {
	// A borrowed session must not spawn a replacement Chrome (it would collide on
	// the shared profile lock); surface the lost connection instead (backlog #13).
	if s.borrowed {
		return fmt.Errorf("reused browser connection lost")
	}
	s.Close()
	log.Print("[browser] session died; relaunching…")
	s.waitProfileReleased(5 * time.Second)
	return s.start()
}

// waitProfileReleased blocks until the profile's SingletonLock is gone (the old
// Chrome has exited) or the deadline passes. No-op for a throwaway profile.
func (s *Session) waitProfileReleased(max time.Duration) {
	if s.opts.ProfileDir == "" {
		return
	}
	dir := s.opts.ProfileDir
	if abs, err := filepath.Abs(dir); err == nil {
		dir = abs
	}
	lock := filepath.Join(dir, "SingletonLock")
	deadline := time.Now().Add(max)
	for time.Now().Before(deadline) {
		if _, err := os.Lstat(lock); os.IsNotExist(err) {
			return
		}
		time.Sleep(100 * time.Millisecond)
	}
}

// alive reports whether the session context is still usable.
func (s *Session) alive() bool { return s.Ctx != nil && s.Ctx.Err() == nil }

// Interrupted reports whether the interrupt context has been canceled (e.g. the
// user pressed Ctrl+C). Long fetch loops check this to stop cleanly between
// items and avoid persisting a half-scraped one.
func (s *Session) Interrupted() bool { return s.interrupt != nil && s.interrupt.Err() != nil }

// ConnectionLost reports whether a navigation gave up after the internet
// connection stayed down past ConnRetryBudget. Fetch loops check it (alongside
// Interrupted) to stop the run cleanly rather than pushing on with a dead
// connection and saving half-scraped items.
func (s *Session) ConnectionLost() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.connLost
}

// markConnLost records that the connection-retry budget was exhausted.
func (s *Session) markConnLost() {
	s.mu.Lock()
	s.connLost = true
	s.mu.Unlock()
}

// interruptDone returns the interrupt context's Done channel, or a nil channel
// (which blocks forever in a select) when there is no interrupt context, so the
// connection-retry wait can be woken by Ctrl+C when one is wired up.
func (s *Session) interruptDone() <-chan struct{} {
	if s.interrupt == nil {
		return nil
	}
	return s.interrupt.Done()
}

// withConnRetry runs attempt and, while it fails with a transient internet
// connectivity error, keeps retrying until the connection recovers or
// ConnRetryBudget elapses. On budget exhaustion it marks the session
// connection-lost (so later navigations short-circuit) and returns
// ErrConnectionLost. Success, or any non-connectivity error, returns at once. A
// user interrupt aborts the wait immediately (returning the last error).
func (s *Session) withConnRetry(attempt func() error) error {
	// Once the budget has been spent, don't retry again for every remaining
	// navigation in the run — fail fast so the loops can stop.
	if s.ConnectionLost() {
		return ErrConnectionLost
	}
	deadline := time.Now().Add(ConnRetryBudget)
	warned := false
	for {
		err := attempt()
		if err == nil || !isConnErr(err) {
			return err
		}
		if !warned {
			logx.Errf("Internet connection error (%v) — retrying for up to %s…\n", err, ConnRetryBudget)
			warned = true
		}
		if time.Now().After(deadline) {
			s.markConnLost()
			logx.Errf("Internet connection still down after %s — giving up.\n", ConnRetryBudget)
			return ErrConnectionLost
		}
		select {
		case <-time.After(connRetryInterval):
		case <-s.interruptDone():
			return err
		}
	}
}

// allocFlags mirrors the Chrome flags used by the Python launcher.
func allocFlags(o Options) []chromedp.ExecAllocatorOption {
	flags := []chromedp.ExecAllocatorOption{
		chromedp.NoFirstRun,
		chromedp.NoDefaultBrowserCheck,
		chromedp.Flag("disable-extensions", true),
		chromedp.Flag("disable-gpu", true),
		// No --no-sandbox: it's only needed in containers/as root, degrades
		// security, and makes Chrome show an "unsupported command-line flag"
		// warning that can spook corporate sign-in. The desktop sandbox works.
		chromedp.Flag("disable-dev-shm-usage", true),
		chromedp.Flag("disable-background-networking", true),
		chromedp.Flag("disable-background-timer-throttling", true),
		chromedp.Flag("disable-backgrounding-occluded-windows", true),
		chromedp.Flag("disable-breakpad", true),
		chromedp.Flag("disable-client-side-phishing-detection", true),
		chromedp.Flag("disable-default-apps", true),
		chromedp.Flag("disable-hang-monitor", true),
		chromedp.Flag("disable-popup-blocking", true),
		chromedp.Flag("disable-prompt-on-repost", true),
		chromedp.Flag("disable-renderer-backgrounding", true),
		chromedp.Flag("disable-sync", true),
		chromedp.Flag("disable-translate", true),
		chromedp.Flag("metrics-recording-only", true),
		chromedp.Flag("safebrowsing-disable-auto-update", true),
		// Reduce automation fingerprinting (same as the Python version).
		chromedp.Flag("disable-blink-features", "AutomationControlled"),
		chromedp.Flag("password-store", "basic"),
		chromedp.Flag("use-mock-keychain", true),
		// Mute all audio in the scraper's browser instance (every tab) — we
		// never need sound while scraping and it shouldn't disturb the user.
		chromedp.Flag("mute-audio", true),
		// Suppress the "Chrome didn't shut down correctly / restore pages"
		// bubble, since we always tear the browser down programmatically.
		chromedp.Flag("disable-session-crashed-bubble", true),
		chromedp.Flag("restore-last-session", false),
	}
	if o.Headless {
		// The less-detectable "new" headless mode.
		flags = append(flags, chromedp.Flag("headless", "new"))
	}
	if o.ProfileDir != "" {
		abs, err := filepath.Abs(o.ProfileDir)
		if err == nil {
			flags = append(flags, chromedp.UserDataDir(abs))
		}
	}
	if o.DebugPort > 0 {
		// Fixed debug port so other processes can reuse this Chrome (backlog #13).
		// chromedp only auto-adds remote-debugging-port=0 when we don't set one.
		flags = append(flags, chromedp.Flag("remote-debugging-port", strconv.Itoa(o.DebugPort)))
	}
	return flags
}

// Launch starts Chrome and returns a Session. interrupt (usually a
// signal.NotifyContext) is watched: when it fires — Ctrl+C, SIGTERM, or a GUI
// teardown — the browser is closed GRACEFULLY (Browser.close), not killed, so
// Chrome exits cleanly and releases the profile lock. Pass context.Background()
// for a browser with no interrupt.
func Launch(interrupt context.Context, o Options) (*Session, error) {
	s := &Session{interrupt: interrupt, opts: o}
	if err := s.start(); err != nil {
		return nil, err
	}
	if interrupt != nil {
		// On interrupt, close gracefully from here so an in-flight navigation
		// (blocking the caller) is aborted promptly by the browser closing.
		go func() {
			<-interrupt.Done()
			s.Close()
		}()
	}
	return s, nil
}

// Navigate loads url, waits for the body, and returns the rendered page HTML and
// the final URL (after any redirect, e.g. to a sign-in page). It is bounded by
// NavTimeout, and if the session has died it relaunches and retries once so a
// single crashed page doesn't cascade "context canceled" across the whole run.
func (s *Session) Navigate(url string, settle time.Duration) (html, finalURL string, err error) {
	err = s.withConnRetry(func() error {
		html, finalURL = "", ""
		return s.navOnce(url, settle, &html, &finalURL)
	})
	return html, finalURL, err
}

// navOnce performs a single navigation attempt, including the one dead-session
// relaunch retry. Retrying a *lost internet connection* is left to the caller
// (withConnRetry); this returns the raw error so it can classify it.
func (s *Session) navOnce(url string, settle time.Duration, html, finalURL *string) error {
	var err error
	for attempt := 0; attempt < 2; attempt++ {
		if !s.alive() {
			if rerr := s.relaunch(); rerr != nil {
				return fmt.Errorf("browser relaunch failed: %w", rerr)
			}
		}
		ctx, cancel := context.WithTimeout(s.Ctx, NavTimeout)
		err = chromedp.Run(ctx,
			chromedp.Navigate(url),
			chromedp.WaitReady("body", chromedp.ByQuery),
			sleep(settle),
			chromedp.Location(finalURL),
			chromedp.OuterHTML("html", html, chromedp.ByQuery),
		)
		cancel()
		if err == nil {
			return nil
		}
		// If the session itself crashed (parent ctx canceled), relaunch and
		// retry once. A per-nav timeout (parent still alive) is just reported.
		if !s.alive() && attempt == 0 {
			continue
		}
		return err
	}
	return err
}

// run executes actions bounded by timeout on the current session context. Used
// by the non-navigating helpers (eval, cookies, page html).
func (s *Session) run(timeout time.Duration, actions ...chromedp.Action) error {
	if !s.alive() {
		return context.Canceled
	}
	ctx, cancel := context.WithTimeout(s.Ctx, timeout)
	defer cancel()
	return chromedp.Run(ctx, actions...)
}

// DefaultProfileDir returns the shared profile path under the CWD, or a throwaway
// (empty) when the CWD can't be determined. Overridable via CSB_PROFILE_DIR env
// or config paths.profile.
func DefaultProfileDir() string {
	if _, err := os.Getwd(); err != nil {
		return ""
	}
	return config.Resolve("CSB_PROFILE_DIR", config.Get().Paths.Profile, ProfileDirName)
}

// quietErrorf drops chromedp's noisy "unhandled node event" CDP messages (which
// are informational, not fetch failures) while still surfacing real errors.
func quietErrorf(format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	if strings.Contains(msg, "unhandled node event") {
		return
	}
	log.Print(msg)
}

// sleep is chromedp.Sleep but tolerant of a zero duration.
func sleep(d time.Duration) chromedp.Action {
	if d <= 0 {
		d = 1 * time.Millisecond
	}
	return chromedp.Sleep(d)
}
