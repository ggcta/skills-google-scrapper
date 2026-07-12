package cli

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"time"

	"csb/internal/pdfgen"
	"csb/internal/store"
)

// cmdDB manages stored items (backlog #17): review, delete, and rename the items
// recorded in the database, so bogus or mis-keyed entries (e.g. a path id that
// isn't a real path, saved as a data-less stub) can be cleaned up. Actions:
//
//	db list [-p|-c|-l]              review items (flags data-less stubs)
//	db show -p/-c/-l <id>           inspect one item and its files
//	db rm   -p/-c/-l <ids> [--yes] [--materials]
//	db set  -p/-c/-l <id> --name "New name"
func cmdDB(args []string) int {
	p := parseArgs(args, map[string]bool{"--name": true})
	action := ""
	if len(p.positionals) > 0 {
		action = strings.ToLower(p.positionals[0])
	}
	switch action {
	case "list", "ls", "":
		return dbList(p)
	case "show", "info":
		return dbShow(p)
	case "rm", "remove", "delete", "del":
		return dbRemove(p)
	case "set", "rename", "mv":
		return dbSet(p)
	default:
		fmt.Fprintf(os.Stderr, "Unknown db action %q. Use: list, show, rm, set.\n", action)
		return 1
	}
}

// dbTable resolves the item type from the -p/-c/-l flags (empty when none).
func dbTable(p parsed) string {
	switch {
	case p.has("-c", "--course", "--courses"):
		return "courses"
	case p.has("-l", "--lab", "--labs"):
		return "labs"
	case p.has("-p", "--path", "--paths"):
		return "paths"
	}
	return ""
}

// dbIDs collects ids from the positional args after the action, splitting each on
// commas/spaces so "db rm -c 60,264" and "db rm -c 60 264" both work.
func dbIDs(p parsed) []string {
	var ids []string
	for _, tok := range p.positionals[1:] {
		ids = append(ids, splitIDs(tok)...)
	}
	return ids
}

func dbList(p parsed) int {
	tables := []string{"paths", "courses", "labs"}
	if t := dbTable(p); t != "" {
		tables = []string{t}
	}
	for _, table := range tables {
		docs, err := store.LoadTable(p.portal, table)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error reading %s: %v\n", table, err)
			return 1
		}
		fmt.Printf("\n%s [%s] — %d item(s):\n", capitalize(table), p.portal, len(docs))
		for _, d := range docs {
			id := d.ID()
			ms, fetched := store.FetchStatus(p.portal, table, id)
			status := "⚠ stub (no data)"
			if fetched {
				status = "fetched"
				if ms > 0 {
					status = "fetched " + time.UnixMilli(ms).Format("2006-01-02")
				}
			}
			fmt.Printf("  %-8s %-52s %s\n", id, truncate(d.Name(), 52), status)
		}
	}
	return 0
}

func dbShow(p parsed) int {
	table := dbTable(p)
	ids := dbIDs(p)
	if table == "" || len(ids) == 0 {
		fmt.Println("Usage: db show -p/-c/-l <id>")
		return 1
	}
	id := ids[0]
	fmt.Printf("%s %s [%s]\n", capitalize(strings.TrimSuffix(table, "s")), id, p.portal)
	fmt.Printf("  name:   %q\n", store.LookupName(p.portal, table, id))
	jsonPath := store.ItemJSONPath(p.portal, table, id)
	fmt.Printf("  json:   %s%s\n", jsonPath, existsMark(jsonPath))
	if md, err := store.MarkdownPathForID(p.portal, table, id); err == nil {
		fmt.Printf("  md:     %s%s\n", md, existsMark(md))
		pdf := pdfgen.PdfPathForMD(md)
		fmt.Printf("  pdf:    %s%s\n", pdf, existsMark(pdf))
	}
	if !store.RowExists(p.portal, table, id) && !fileExists(jsonPath) {
		fmt.Println("  (not found in the database)")
	}
	return 0
}

func dbRemove(p parsed) int {
	table := dbTable(p)
	ids := dbIDs(p)
	if table == "" || len(ids) == 0 {
		fmt.Println("Usage: db rm -p/-c/-l <ids> [--yes] [--materials]")
		return 1
	}
	if !p.has("--yes", "-y") {
		fmt.Printf("Delete %d %s %v from [%s]? This cannot be undone. [y/N] ",
			len(ids), table, ids, p.portal)
		reader := bufio.NewReader(os.Stdin)
		ans, _ := reader.ReadString('\n')
		if a := strings.ToLower(strings.TrimSpace(ans)); a != "y" && a != "yes" {
			fmt.Println("Aborted.")
			return 0
		}
	}

	rc := 0
	for _, id := range ids {
		var removed []string
		// Derived vault files (their names come from the item's title).
		if md, err := store.MarkdownPathForID(p.portal, table, id); err == nil {
			removeIfExists(md, &removed)
			removeIfExists(pdfgen.PdfPathForMD(md), &removed)
		}
		// Per-item JSON (the SSOT).
		removeIfExists(store.ItemJSONPath(p.portal, table, id), &removed)
		// Shared materials, only when explicitly asked (keyed globally by id).
		if p.has("--materials", "--purge") {
			removeDirIfExists(store.MaterialsDir(table, id), &removed)
		}
		// Ledger row.
		if ok, err := store.DeleteLedgerRow(p.portal, table, id); err != nil {
			fmt.Fprintf(os.Stderr, "  error removing %s %s row: %v\n", table, id, err)
			rc = 1
		} else if ok {
			removed = append(removed, "database.json row")
		}

		if len(removed) == 0 {
			fmt.Printf("%s %s: nothing to remove (not in the database).\n",
				capitalize(strings.TrimSuffix(table, "s")), id)
			continue
		}
		fmt.Printf("Deleted %s %s [%s]:\n", strings.TrimSuffix(table, "s"), id, p.portal)
		for _, r := range removed {
			fmt.Printf("  - %s\n", r)
		}
	}
	return rc
}

func dbSet(p parsed) int {
	table := dbTable(p)
	ids := dbIDs(p)
	name, hasName := p.value("--name")
	if table == "" || len(ids) == 0 || !hasName {
		fmt.Println(`Usage: db set -p/-c/-l <id> --name "New name"`)
		return 1
	}
	id := ids[0]
	oldMd, err := store.SetItemName(p.portal, table, id, name)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error renaming %s %s: %v\n", table, id, err)
		return 1
	}
	// The old .md/.pdf filenames no longer match the new title; drop the stale
	// derived files (regenerate with `md`/`pdf` when needed).
	if oldMd != "" {
		var removed []string
		removeIfExists(oldMd, &removed)
		removeIfExists(pdfgen.PdfPathForMD(oldMd), &removed)
	}
	fmt.Printf("Renamed %s %s [%s] to %q.\n", strings.TrimSuffix(table, "s"), id, p.portal, name)
	return 0
}

// --- small helpers ---

func removeIfExists(path string, removed *[]string) {
	if path == "" {
		return
	}
	if err := os.Remove(path); err == nil {
		*removed = append(*removed, path)
	}
}

func removeDirIfExists(dir string, removed *[]string) {
	if dir == "" {
		return
	}
	if info, err := os.Stat(dir); err == nil && info.IsDir() {
		if os.RemoveAll(dir) == nil {
			*removed = append(*removed, dir+"/")
		}
	}
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func existsMark(path string) string {
	if fileExists(path) {
		return "  (exists)"
	}
	return "  (missing)"
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n-1]) + "…"
}
