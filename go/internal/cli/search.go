package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"csb/internal/store"
)

// cmdSearch searches the local database, matching the Python behaviour: a
// whole-document case-insensitive substring match, or a single-field match
// (list-aware) when --field is given.
func cmdSearch(args []string) int {
	p := parseArgs(args, map[string]bool{"--field": true, "-f": true})
	if len(p.positionals) == 0 {
		fmt.Println("Please provide a search query.")
		return 1
	}
	query := strings.ToLower(p.positionals[0])
	field, _ := p.value("--field", "-f")

	var tables []string
	switch {
	case p.has("--course", "-c"):
		tables = []string{"courses"}
	case p.has("--path", "-p"):
		tables = []string{"paths"}
	case p.has("--lab", "-l"):
		tables = []string{"labs"}
	default:
		tables = []string{"paths", "courses", "labs"}
	}

	jsonOut := p.has("--json")
	tablesRepr := pyListRepr(tables)
	if !jsonOut {
		if field == "" {
			fmt.Printf("Searching for '%s' in %s...\n", p.positionals[0], tablesRepr)
		} else {
			fmt.Printf("Searching for '%s' in %s (field: %s)...\n", p.positionals[0], tablesRepr, field)
		}
	}

	var jsonResults []jsonItem
	total := 0
	for _, table := range tables {
		docs, err := store.LoadTable(p.portal, table)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error reading %s: %v\n", table, err)
			continue
		}
		var matched []store.Doc
		for _, d := range docs {
			if docMatches(d, query, field) {
				matched = append(matched, d)
			}
		}
		if jsonOut {
			for _, d := range matched {
				jsonResults = append(jsonResults, newJSONItem(p.portal, table, d.ID(), d.Name()))
			}
			total += len(matched)
			continue
		}
		if len(matched) > 0 {
			fmt.Printf("\n--- %s (%d) ---\n", table, len(matched))
			for _, d := range matched {
				id := d.ID()
				if id == "" {
					id = "N/A"
				}
				name := d.Name()
				if name == "" {
					name = "N/A"
				}
				fmt.Printf("+|-• \033[35m[%5s - %-72s]\033[0m %s\n", id, name, fetchStatusText(p.portal, table, d.ID()))
			}
			total += len(matched)
		}
	}
	if jsonOut {
		if jsonResults == nil {
			jsonResults = []jsonItem{}
		}
		emitJSON(jsonResults)
		return 0
	}
	if total == 0 {
		fmt.Println("No results found.")
	}
	return 0
}

// pyListRepr renders a string slice like Python's list repr: ['a', 'b'].
func pyListRepr(items []string) string {
	quoted := make([]string, len(items))
	for i, it := range items {
		quoted[i] = "'" + it + "'"
	}
	return "[" + strings.Join(quoted, ", ") + "]"
}

func docMatches(d store.Doc, query, field string) bool {
	if field != "" {
		v, ok := d[field]
		if !ok || v == nil {
			return false
		}
		switch val := v.(type) {
		case []any:
			for _, item := range val {
				if strings.Contains(strings.ToLower(fmt.Sprint(item)), query) {
					return true
				}
			}
			return false
		default:
			return strings.Contains(strings.ToLower(fmt.Sprint(val)), query)
		}
	}
	// Whole-document match: serialise values and substring-search.
	b, err := json.Marshal(d)
	if err != nil {
		return false
	}
	return strings.Contains(strings.ToLower(string(b)), query)
}
