package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"csb/internal/browser"
	"csb/internal/portal"
	"csb/internal/store"
)

// cmdList lists stored paths, courses, or labs from the local database.
// (--reload, which refreshes from the website, arrives with the browser slice.)
func cmdList(args []string) int {
	p := parseArgs(args, nil)

	table, label := "paths", "paths"
	switch {
	case p.has("--courses", "-c"):
		table, label = "courses", "courses"
	case p.has("--labs", "-l"):
		table, label = "labs", "labs"
	case p.has("--paths", "-p"):
		table, label = "paths", "paths"
	}

	if p.has("--reload", "-r") {
		if err := reloadList(p.portal, table, p.has("--headless")); err != nil {
			fmt.Fprintf(os.Stderr, "reload error: %v\n", err)
		}
	}

	jsonOut := p.has("--json")
	docs, err := store.LoadTable(p.portal, table)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	if !jsonOut {
		fmt.Printf("Listing all %s [%s]...\n", label, p.portal)
	}
	if len(docs) == 0 {
		if jsonOut {
			emitJSON([]jsonItem{})
			return 0
		}
		fmt.Printf("No %s found locally.\n", label)
		if !p.has("--reload", "-r") {
			// First-run guidance: the local database starts empty; the catalog
			// has to be pulled from the website once.
			kindFlag := map[string]string{"paths": "-p", "courses": "-c", "labs": "-l"}[table]
			fmt.Printf("Tip: fetch the catalog from the website with:  skills-scraper list -r %s %s\n",
				portalFlag(p.portal), kindFlag)
		}
		return 0
	}

	type row struct{ id, name string }
	rows := make([]row, 0, len(docs))
	for _, d := range docs {
		rows = append(rows, row{d.ID(), d.Name()})
	}

	sortByID := p.has("--id", "-i")
	sort.SliceStable(rows, func(i, j int) bool {
		if sortByID {
			return rows[i].id < rows[j].id
		}
		return rows[i].name < rows[j].name
	})

	// Structured output for GUI/scripting consumers.
	if p.has("--json") {
		out := make([]jsonItem, len(rows))
		for i, r := range rows {
			out[i] = newJSONItem(p.portal, table, r.id, r.name)
		}
		emitJSON(out)
		return 0
	}

	fmt.Printf("\n\033[45m[%s]\033[0m\n\n", center(strings.ToUpper(label), 85))
	for _, r := range rows {
		fmt.Printf("+|-• \033[35m[%5s - %-72s]\033[0m %s\n", r.id, r.name, fetchStatusText(p.portal, table, r.id))
	}
	return 0
}

// reloadList refreshes a catalog list (paths/courses/labs) from the site's JSON
// API and upserts id/name into the database (ports Collection.fetch_*). It owns
// its browser session; callers that already have one use reloadListWith.
func reloadList(portalKey, table string, headless bool) error {
	// Signal-aware context so Ctrl+C / SIGTERM during a reload tears Chrome down.
	ctx, stop := browserSignalContext()
	defer stop()
	// Reuse the persistent "browser" window if one is open and reachable (#13),
	// otherwise launch our own.
	opts := browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   headless,
	}
	if ws, ok := browser.LoadEndpoint(); ok && browser.EndpointAlive(ws) {
		opts = browser.Options{RemoteWS: ws}
	}
	sess, err := browser.Launch(ctx, opts)
	if err != nil {
		return err
	}
	defer sess.Close()
	return reloadListWith(sess, portalKey, table)
}

// reloadListWith refreshes a catalog list using an existing browser session.
func reloadListWith(sess *browser.Session, portalKey, table string) error {
	cfg := portal.Get(portalKey)
	apiURL := map[string]string{
		"paths":   cfg.APIPaths,
		"courses": cfg.APICourses,
		"labs":    cfg.APILabs,
	}[table]
	fmt.Fprintf(os.Stderr, "Reloading %s list from remote [%s] (this can take a moment)...\n", table, portalKey)

	found := 0
	for page := 1; page <= 100; page++ {
		// Per-page progress so a multi-page catalog fetch doesn't look hung.
		fmt.Fprintf(os.Stderr, "  fetching page %d… (%d %s so far)\r", page, found, table)
		text, err := sess.FetchText(fmt.Sprintf("%s&page=%d", apiURL, page))
		if err != nil {
			return err
		}
		items, err := parseCatalogItems(text)
		if err != nil {
			return fmt.Errorf("decode page %d: %w", page, err)
		}
		if len(items) == 0 {
			break
		}
		for _, it := range items {
			clean := strings.Split(it.Path, "?")[0]
			parts := strings.Split(clean, "/")
			id := parts[len(parts)-1]
			if id != "" && it.Title != "" {
				if err := store.UpsertCollectionName(portalKey, table, id, strings.TrimSpace(it.Title)); err != nil {
					return err
				}
				found++
			}
		}
	}
	fmt.Fprint(os.Stderr, "\r\033[K") // clear the progress line
	fmt.Fprintf(os.Stderr, "Total %s found: %d\n", table, found)
	return nil
}

type catalogItem struct {
	Title string `json:"title"`
	Path  string `json:"path"`
}

// parseCatalogItems handles both a bare array and a {searchResults: [...]} object.
func parseCatalogItems(text string) ([]catalogItem, error) {
	text = strings.TrimSpace(text)
	if text == "" {
		return nil, nil
	}
	if strings.HasPrefix(text, "[") {
		var arr []catalogItem
		if err := json.Unmarshal([]byte(text), &arr); err != nil {
			return nil, err
		}
		return arr, nil
	}
	var obj struct {
		SearchResults []catalogItem `json:"searchResults"`
	}
	if err := json.Unmarshal([]byte(text), &obj); err != nil {
		return nil, err
	}
	return obj.SearchResults, nil
}

// center pads s to width, centered (mirrors Python's :^N format).
func center(s string, width int) string {
	if len(s) >= width {
		return s
	}
	total := width - len(s)
	left := total / 2
	right := total - left
	return strings.Repeat(" ", left) + s + strings.Repeat(" ", right)
}
