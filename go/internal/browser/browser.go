// Package browser launches Chrome via chromedp, mirroring the Python
// launch_browser: it reuses the same persistent profile folder (so a sign-in
// done from either the Python or Go tool carries over) and applies the same
// anti-automation flags. Headless uses the less-detectable "new" mode.
package browser

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/chromedp/chromedp"
)

// ProfileDirName is the default reusable profile folder (matches the Python
// WEBDRIVER_PROFILE_FOLDER_NAME), resolved under the current working directory.
const ProfileDirName = ".webdriver_profiles"

// Options configure a browser launch.
type Options struct {
	// ProfileDir is the user-data-dir. Empty means a throwaway profile.
	ProfileDir string
	// Headless runs Chrome with --headless=new when true.
	Headless bool
}

// NavTimeout bounds a single navigation/evaluation so a page that hangs (e.g. a
// body that never becomes ready) can't block the whole run forever. It is a var
// so tests can shorten it.
var NavTimeout = 45 * time.Second

// Session is a running browser. Call Close when done. It is self-healing: if the
// underlying browser/tab dies (its context is canceled), the next navigation
// transparently relaunches it, reusing the same on-disk profile so the sign-in
// carries over.
type Session struct {
	Ctx    context.Context
	parent context.Context
	opts   Options
	cancel []func()
}

// Close tears down the browser and allocator.
func (s *Session) Close() {
	for i := len(s.cancel) - 1; i >= 0; i-- {
		s.cancel[i]()
	}
	s.cancel = nil
}

// start launches a fresh browser and wires up s.Ctx / s.cancel.
func (s *Session) start() error {
	allocCtx, cancelAlloc := chromedp.NewExecAllocator(s.parent, allocFlags(s.opts)...)
	ctx, cancelCtx := chromedp.NewContext(allocCtx, chromedp.WithErrorf(quietErrorf))
	// Force the browser process to actually start so profile/allocator errors
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

// allocFlags mirrors the Chrome flags used by the Python launcher.
func allocFlags(o Options) []chromedp.ExecAllocatorOption {
	flags := []chromedp.ExecAllocatorOption{
		chromedp.NoFirstRun,
		chromedp.NoDefaultBrowserCheck,
		chromedp.Flag("disable-extensions", true),
		chromedp.Flag("disable-gpu", true),
		chromedp.Flag("no-sandbox", true),
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
	return flags
}

// Launch starts Chrome and returns a Session.
func Launch(parent context.Context, o Options) (*Session, error) {
	s := &Session{parent: parent, opts: o}
	if err := s.start(); err != nil {
		return nil, err
	}
	return s, nil
}

// Navigate loads url, waits for the body, and returns the rendered page HTML and
// the final URL (after any redirect, e.g. to a sign-in page). It is bounded by
// NavTimeout, and if the session has died it relaunches and retries once so a
// single crashed page doesn't cascade "context canceled" across the whole run.
func (s *Session) Navigate(url string, settle time.Duration) (html, finalURL string, err error) {
	for attempt := 0; attempt < 2; attempt++ {
		if !s.alive() {
			if rerr := s.relaunch(); rerr != nil {
				return "", "", fmt.Errorf("browser relaunch failed: %w", rerr)
			}
		}
		ctx, cancel := context.WithTimeout(s.Ctx, NavTimeout)
		err = chromedp.Run(ctx,
			chromedp.Navigate(url),
			chromedp.WaitReady("body", chromedp.ByQuery),
			sleep(settle),
			chromedp.Location(&finalURL),
			chromedp.OuterHTML("html", &html, chromedp.ByQuery),
		)
		cancel()
		if err == nil {
			return html, finalURL, nil
		}
		// If the session itself crashed (parent ctx canceled), relaunch and
		// retry once. A per-nav timeout (parent still alive) is just reported.
		if !s.alive() && attempt == 0 {
			continue
		}
		return html, finalURL, err
	}
	return html, finalURL, err
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
// (empty) when the CWD can't be determined.
func DefaultProfileDir() string {
	if _, err := os.Getwd(); err != nil {
		return ""
	}
	return ProfileDirName
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
