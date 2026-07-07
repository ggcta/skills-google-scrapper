package cli

import (
	"bufio"
	"context"
	"fmt"
	"os"

	"github.com/chromedp/chromedp"

	"csb/internal/browser"
	"csb/internal/portal"
)

// cmdLogin opens a visible browser at the portal home page so the user can sign
// in; the session persists in the shared profile for later fetches. Ports the
// Python cmd_login (no scraping).
func cmdLogin(args []string) int {
	p := parseArgs(args, nil)
	url := portal.Get(p.portal).Base

	fmt.Printf("\nLaunching browser to sign in to the '%s' portal...\n", p.portal)
	fmt.Printf("Opening: %s\n", url)

	sess, err := browser.Launch(context.Background(), browser.Options{
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
	bufio.NewReader(os.Stdin).ReadString('\n')

	fmt.Printf("Done. Your '%s' session is saved to the browser profile.\n", p.portal)
	return 0
}
