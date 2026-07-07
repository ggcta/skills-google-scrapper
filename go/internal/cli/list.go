package cli

import (
	"fmt"
	"os"
	"sort"
	"strings"

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
		fmt.Println("Note: --reload needs the browser and is not wired up in the Go build yet; listing from local data.")
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
