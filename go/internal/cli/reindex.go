package cli

import (
	"fmt"
	"os"

	"csb/internal/store"
)

// cmdReindex rebuilds the TinyDB ledger (database.json) for a portal from the
// per-item JSON files — the single source of truth (backlog #9). Use it to
// recover the index after database.json is lost or to normalize legacy rows.
// It never touches the per-item files.
func cmdReindex(args []string) int {
	p := parseArgs(args, nil)
	total := 0
	for _, table := range []string{"paths", "courses", "labs"} {
		n, err := store.ReindexTable(p.portal, table)
		if err != nil {
			fmt.Fprintf(os.Stderr, "reindex %s [%s]: %v\n", table, p.portal, err)
			return 1
		}
		fmt.Printf("Reindexed %d %s from files [%s]\n", n, table, p.portal)
		total += n
	}
	fmt.Printf("Reindex complete: %d fetched items indexed [%s]\n", total, p.portal)
	return 0
}
