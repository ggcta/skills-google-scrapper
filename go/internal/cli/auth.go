package cli

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"time"

	"csb/internal/browser"
	"csb/internal/logx"
)

// stdinReader is shared so successive auth prompts don't drop buffered input.
// For the GUI, the fetch subprocess's stdin is piped and the GUI writes a
// newline to continue; for the CLI it's the terminal.
var stdinReader = bufio.NewReader(os.Stdin)

// ensureAuthenticated re-navigates through a redirect to the sign-in page: while
// finalURL is a sign-in URL it prompts the user to sign in in the live browser
// window, waits, then reloads url — until authenticated — REUSING the same
// browser session (backlog #2/#3, cascaded from Python util_ensure_authenticated).
// It returns the authenticated page HTML. A machine-readable "@@AUTH_REQUIRED"
// marker is emitted so a wrapping GUI can surface a sign-in prompt; the CLI user
// just presses Enter.
func ensureAuthenticated(sess *browser.Session, url, html, finalURL string, settle time.Duration, desc string) (string, error) {
	suffix := ""
	if desc != "" {
		suffix = " for " + desc
	}
	for strings.Contains(finalURL, "sign_in") {
		if sess.Interrupted() {
			return html, errInterrupted
		}
		// Machine marker on stdout (like @@ITEM), only when a GUI asked for it via
		// --emit-progress; the human prompt on stderr shows for everyone.
		if emitProgress {
			logx.Raw(fmt.Sprintf("@@AUTH_REQUIRED %s\n", url))
		}
		fmt.Fprintf(os.Stderr, "\n[!] Sign-in required%s — please sign in in the browser window.\n", suffix)
		fmt.Fprint(os.Stderr, "Press Enter after you have signed in to continue... ")

		if _, err := stdinReader.ReadString('\n'); err != nil {
			// EOF / closed stdin: nothing more we can do.
			return html, fmt.Errorf("authentication aborted%s", suffix)
		}

		var err error
		html, finalURL, err = sess.Navigate(url, settle)
		if err != nil {
			return html, err
		}
	}
	return html, nil
}
