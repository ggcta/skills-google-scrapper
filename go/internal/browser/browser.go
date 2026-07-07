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

// Session is a running browser. Call Close when done.
type Session struct {
	Ctx    context.Context
	cancel []func()
}

// Close tears down the browser and allocator.
func (s *Session) Close() {
	for i := len(s.cancel) - 1; i >= 0; i-- {
		s.cancel[i]()
	}
}

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
	allocCtx, cancelAlloc := chromedp.NewExecAllocator(parent, allocFlags(o)...)
	ctx, cancelCtx := chromedp.NewContext(allocCtx, chromedp.WithErrorf(quietErrorf))
	// Force the browser process to actually start so profile/allocator errors
	// surface here rather than on first navigate.
	if err := chromedp.Run(ctx); err != nil {
		cancelCtx()
		cancelAlloc()
		return nil, err
	}
	return &Session{Ctx: ctx, cancel: []func(){cancelCtx, cancelAlloc}}, nil
}

// Navigate loads url, waits for the body, and returns the rendered page HTML
// and the final URL (after any redirect, e.g. to a sign-in page).
func (s *Session) Navigate(url string, settle time.Duration) (html, finalURL string, err error) {
	err = chromedp.Run(s.Ctx,
		chromedp.Navigate(url),
		chromedp.WaitReady("body", chromedp.ByQuery),
		sleep(settle),
		chromedp.Location(&finalURL),
		chromedp.OuterHTML("html", &html, chromedp.ByQuery),
	)
	return html, finalURL, err
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
