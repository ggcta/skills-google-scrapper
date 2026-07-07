package cli

import (
	"context"
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

	docs, err := store.LoadTable(p.portal, table)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	fmt.Printf("Listing all %s [%s]...\n", label, p.portal)
	if len(docs) == 0 {
		fmt.Printf("No %s found locally.\n", label)
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

	fmt.Printf("\n\033[45m[%s]\033[0m\n\n", center(strings.ToUpper(label), 85))
	for _, r := range rows {
		fmt.Printf("+|-• \033[35m[%5s - %-72s]\033[0m\n", r.id, r.name)
	}
	return 0
}

// reloadList refreshes a catalog list (paths/courses/labs) from the site's JSON
// API and upserts id/name into the database (ports Collection.fetch_*).
func reloadList(portalKey, table string, headless bool) error {
	cfg := portal.Get(portalKey)
	apiURL := map[string]string{
		"paths":   cfg.APIPaths,
		"courses": cfg.APICourses,
		"labs":    cfg.APILabs,
	}[table]
	fmt.Printf("Reloading %s list from remote [%s]...\n", table, portalKey)

	sess, err := browser.Launch(context.Background(), browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   headless,
	})
	if err != nil {
		return err
	}
	defer sess.Close()

	found := 0
	for page := 1; page <= 100; page++ {
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
	fmt.Printf("Total %s found: %d\n", table, found)
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
