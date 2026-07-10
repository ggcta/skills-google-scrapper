package cli

import (
	"errors"
	"fmt"
	"os"

	"csb/internal/store"
)

// cmdMDPath prints the absolute vault .md path for a single stored item, or
// exits non-zero with a message if it isn't fetched (exit 1) or was fetched
// without Markdown (exit 2). Used by the GUI to open an item's Markdown on
// double-click, and handy on its own: `open "$(skills-scraper mdpath -c 53)"`.
func cmdMDPath(args []string) int {
	p := parseArgs(args, map[string]bool{
		"-c": true, "--course": true, "--courses": true,
		"-p": true, "--path": true, "--paths": true,
		"-l": true, "--lab": true, "--labs": true,
	})

	var table, raw string
	if v, ok := p.value("-c", "--course", "--courses"); ok {
		table, raw = "courses", v
	} else if v, ok := p.value("-p", "--path", "--paths"); ok {
		table, raw = "paths", v
	} else if v, ok := p.value("-l", "--lab", "--labs"); ok {
		table, raw = "labs", v
	} else {
		fmt.Fprintln(os.Stderr, "mdpath: specify the item with -p, -c, or -l <id>")
		return 1
	}

	pk, id := resolvePortal(raw, p.portal)
	path, err := store.MarkdownPathForID(pk, table, id)
	if err != nil {
		if errors.Is(err, store.ErrNotStored) {
			fmt.Fprintf(os.Stderr, "not fetched yet: %s %s [%s]\n", table, id, pk)
			return 1
		}
		fmt.Fprintf(os.Stderr, "mdpath: %v\n", err)
		return 1
	}
	if _, err := os.Stat(path); err != nil {
		fmt.Fprintf(os.Stderr, "markdown not found (fetched with --no-md?): %s\n", path)
		return 2
	}
	fmt.Println(path)
	return 0
}
