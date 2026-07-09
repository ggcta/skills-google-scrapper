// Package cli implements the command-line interface, mirroring the Python
// argparse surface (commands, aliases, and -A/-B portal flags).
package cli

import (
	"fmt"
	"os"
	"strings"

	"csb/internal/portal"
)

// Run dispatches a command. Returns a process exit code.
func Run(args []string) int {
	if len(args) == 0 {
		printUsage()
		return 1
	}
	cmd := args[0]
	rest := args[1:]

	switch cmd {
	case "list", "l":
		return cmdList(rest)
	case "fetch", "f":
		return cmdFetch(rest)
	case "md":
		return cmdMD(rest)
	case "search", "s":
		return cmdSearch(rest)
	case "login":
		return cmdLogin(rest)
	case "interactive", "i":
		return cmdInteractive(rest)
	case "-h", "--help", "help":
		printUsage()
		return 0
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", cmd)
		printUsage()
		return 1
	}
}

func printUsage() {
	fmt.Println(`skills-scraper — Google Skills Scraper (Go)

Usage: skills-scraper <command> [options]

Commands:
  list, l        List stored paths, courses, or labs
  fetch, f       Fetch (scrape) courses/paths/labs into Markdown + JSON
  md             (Re)generate Markdown from stored data (no browser)
  search, s      Search the local database
  login          Sign in to a portal (opens a browser)
  interactive, i Launch the interactive menu

Portal flags (most commands):
  -A, -a, --public    Public portal (default)
  -B, -b, --partner   Partner portal
  --portal, -P NAME   Explicit portal name

Fetch options (fetch):
  -p/-c/-l <ids>      Paths / courses / labs to fetch (comma or space separated)
  --all [kind]        Fetch the whole catalog (paths|courses|labs|all); reloads first
  -f, --force         Re-fetch items even if already stored
  -t, --toc           Table-of-contents only (skip step bodies)
  --no-transcript     Fetch full pages but skip video transcripts
  --no-md             Write JSON only, skip Markdown
  --headless          Run Chrome without a visible window
  --log-dir PATH      Directory for the per-run activity log (default ./logs,
                      or set CSB_LOG_DIR)

List options (list):
  -r, --reload        Refresh the catalog from the website first (opens Chrome)
  -i, --id            Sort by id instead of name
  --headless          Reload without a visible browser window
  --json              Machine-readable output (used by the GUI)`)
}

// flagSet is a tiny argument scanner shared by the commands. It recognises the
// portal flags and collects the remaining tokens, so each command can pick out
// the options it cares about.
type parsed struct {
	portal string
	// boolFlags that were seen (e.g. "--toc", "-t")
	bools map[string]bool
	// valueFlags map a flag to its value (e.g. "-c" -> "53,54")
	values map[string]string
	// positionals are non-flag args
	positionals []string
}

func (p parsed) has(names ...string) bool {
	for _, n := range names {
		if p.bools[n] {
			return true
		}
	}
	return false
}

func (p parsed) value(names ...string) (string, bool) {
	for _, n := range names {
		if v, ok := p.values[n]; ok {
			return v, true
		}
	}
	return "", false
}

// parseArgs scans args. valueFlagNames lists flags that consume the next token
// as their value; everything else is treated as a boolean flag or positional.
func parseArgs(args []string, valueFlagNames map[string]bool) parsed {
	p := parsed{portal: portal.Default, bools: map[string]bool{}, values: map[string]string{}}
	for i := 0; i < len(args); i++ {
		a := args[i]
		switch a {
		case "-A", "-a", "--public":
			p.portal = "public"
			continue
		case "-B", "-b", "--partner":
			p.portal = "partner"
			continue
		case "--portal", "-P":
			if i+1 < len(args) {
				i++
				p.portal = args[i]
			}
			continue
		}
		// --portal=name form
		if strings.HasPrefix(a, "--portal=") {
			p.portal = strings.TrimPrefix(a, "--portal=")
			continue
		}
		if strings.HasPrefix(a, "-") {
			// value flag?
			if valueFlagNames[a] {
				if i+1 < len(args) {
					i++
					p.values[a] = args[i]
				}
				continue
			}
			// --flag=value general form
			if eq := strings.Index(a, "="); eq >= 0 && strings.HasPrefix(a, "--") {
				p.values[a[:eq]] = a[eq+1:]
				continue
			}
			p.bools[a] = true
			continue
		}
		p.positionals = append(p.positionals, a)
	}
	return p
}

// splitIDs splits a comma/space separated id list.
func splitIDs(s string) []string {
	f := strings.FieldsFunc(s, func(r rune) bool { return r == ',' || r == ' ' })
	var out []string
	for _, x := range f {
		if x = strings.TrimSpace(x); x != "" {
			out = append(out, x)
		}
	}
	return out
}
