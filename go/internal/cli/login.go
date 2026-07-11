package cli

import (
	"bufio"
	"fmt"
	"os"

	"github.com/chromedp/chromedp"

	"csb/internal/browser"
	"csb/internal/portal"
)

// cmdLogin opens a visible browser at the portal home page so the user can sign
// in; the session persists in the shared profile for later fetches. Ports the
// Python cmd_login (no scraping). It also stops on SIGINT/SIGTERM so a wrapping
// GUI can close the sign-in browser without orphaning Chrome (which would keep
// the profile locked and leave the next run unauthenticated).
func cmdLogin(args []string) int {
	p := parseArgs(args, nil)
	url := portal.Get(p.portal).Base

	ctx, stop := browserSignalContext()
	defer stop()

	fmt.Printf("\nLaunching browser to sign in to the '%s' portal...\n", p.portal)
	fmt.Printf("Opening: %s\n", url)

	sess, err := browser.Launch(ctx, browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   false, // login must be visible
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "error launching browser: %v\n", err)
		return 1
	}
	defer sess.Close()

	if err := chromedp.Run(sess.Ctx, chromedp.Navigate(url)); err != nil {
		fmt.Fprintf(os.Stderr, "error opening page: %v\n", err)
		return 1
	}

	fmt.Println("Sign in to the portal in the browser window.")
	fmt.Print("Press Enter when you are done to close the browser...")

	// Wait for the user (Enter) OR a termination signal (GUI teardown / Ctrl+C);
	// either way the deferred sess.Close() tears the browser down cleanly.
	done := make(chan struct{})
	go func() {
		bufio.NewReader(os.Stdin).ReadString('\n')
		close(done)
	}()
	select {
	case <-done:
	case <-ctx.Done():
		fmt.Fprintln(os.Stderr, "\nSign-in canceled; closing the browser.")
	}

	fmt.Printf("Done. Your '%s' session is saved to the browser profile.\n", p.portal)
	return 0
}
