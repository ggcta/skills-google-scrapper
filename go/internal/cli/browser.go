package cli

import (
	"bufio"
	"fmt"
	"os"

	"github.com/chromedp/chromedp"

	"csb/internal/browser"
	"csb/internal/portal"
)

// cmdBrowser opens a visible, long-lived browser the user can sign in and browse
// in, and that later fetch/sync runs REUSE instead of launching their own Chrome
// (backlog #13) — so the site never re-challenges for sign-in between tasks. It
// advertises a remote-debugging endpoint (SaveEndpoint) that those runs connect
// to. Stays open until Enter / stdin close (CLI) or SIGTERM (GUI teardown /
// Ctrl+C); on exit it clears the endpoint and closes Chrome (it owns it).
func cmdBrowser(args []string) int {
	p := parseArgs(args, nil)
	url := portal.Get(p.portal).Base

	ctx, stop := browserSignalContext()
	defer stop()

	port, err := browser.FreePort()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error finding a free port: %v\n", err)
		return 1
	}

	fmt.Printf("\nOpening a reusable browser for the '%s' portal...\n", p.portal)
	sess, err := browser.Launch(ctx, browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   false, // must be visible so the user can sign in / browse
		DebugPort:  port,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "error launching browser: %v\n", err)
		return 1
	}
	defer sess.Close()
	defer browser.ClearEndpoint()

	// Chrome is listening on the debug port now (Launch waited for it); advertise
	// it so fetch/sync can reuse this window.
	if err := browser.SaveEndpoint(port); err != nil {
		fmt.Fprintf(os.Stderr, "warning: could not advertise browser for reuse: %v\n", err)
	}

	if err := chromedp.Run(sess.Ctx, chromedp.Navigate(url)); err != nil {
		fmt.Fprintf(os.Stderr, "error opening page: %v\n", err)
		return 1
	}

	fmt.Println("Browser is open. Sign in and browse freely; fetches will reuse this window.")
	fmt.Print("Press Enter (or close it from the GUI) to close the browser...")

	// Wait for the user (Enter) OR a termination signal (GUI teardown / Ctrl+C);
	// either way the deferred ClearEndpoint + sess.Close tear it down cleanly.
	done := make(chan struct{})
	go func() {
		bufio.NewReader(os.Stdin).ReadString('\n')
		close(done)
	}()
	select {
	case <-done:
	case <-ctx.Done():
		fmt.Fprintln(os.Stderr, "\nClosing the browser.")
	}
	fmt.Println("Browser closed.")
	return 0
}

// cmdBrowserStatus prints whether a reusable browser is advertised and reachable:
// "none" (no persistent browser), "alive" (reachable — will be reused), or
// "stale" (advertised but not responding — the GUI asks the user to close it).
func cmdBrowserStatus(args []string) int {
	ws, ok := browser.LoadEndpoint()
	switch {
	case !ok:
		fmt.Println("none")
	case browser.EndpointAlive(ws):
		fmt.Println("alive")
	default:
		fmt.Println("stale")
	}
	return 0
}
