package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// typeName maps a plural table to the capitalized entity type stored in a row.
var typeName = map[string]string{"paths": "Path", "courses": "Course", "labs": "Lab"}

// ReindexTable rebuilds one ledger table (paths/courses/labs) in database.json
// from the per-item JSON files — the single source of truth (backlog #9). Every
// per-item file becomes a compact ledger row carrying its scrapedTime. Rows that
// exist in the DB but have no file (catalog-only stubs for not-yet-fetched items,
// or items whose data file was deleted) are preserved so the browse catalog and
// last-known status survive; a preserved row keeps its prior scrapedTime, if any.
// The per-item files are never modified. Returns the number of files indexed.
func ReindexTable(portalKey, table string) (int, error) {
	kind := typeName[table]
	if kind == "" {
		return 0, nil
	}

	// Existing rows, so catalog-only stubs (no file) can be preserved.
	existing, _ := LoadTable(portalKey, table)
	prior := make(map[string]Doc, len(existing))
	for _, d := range existing {
		if id := d.ID(); id != "" {
			prior[id] = d
		}
	}

	// Rebuild a row per per-item file.
	dir := filepath.Join(DataRoot(), portalKey, table)
	entries, err := os.ReadDir(dir)
	if err != nil && !os.IsNotExist(err) {
		return 0, err
	}
	rows := map[string]Doc{}
	fetched := 0
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		id := strings.TrimSuffix(e.Name(), ".json")
		var meta struct {
			Title       string `json:"title"`
			ScrapedTime int64  `json:"scrapedTime"`
		}
		if err := loadJSON(filepath.Join(dir, e.Name()), &meta); err != nil {
			continue // skip an unreadable file rather than abort the whole reindex
		}
		rows[id] = Doc{
			"id":          id,
			"name":        meta.Title,
			"title":       meta.Title,
			"type":        kind,
			"portal":      portalKey,
			"scrapedTime": meta.ScrapedTime,
		}
		fetched++
	}

	// Preserve catalog-only stubs (in the DB but with no file), keeping any
	// last-known scrapedTime so a deleted data file doesn't erase the status.
	for id, d := range prior {
		if _, ok := rows[id]; ok {
			continue
		}
		row := Doc{
			"id":     id,
			"name":   d.Name(),
			"title":  d.Name(),
			"type":   kind,
			"portal": portalKey,
		}
		if st, ok := d["scrapedTime"]; ok {
			row["scrapedTime"] = st
		}
		rows[id] = row
	}

	return fetched, writeTable(portalKey, table, rows)
}

// writeTable replaces one table in database.json with rows keyed by sequential
// integer strings (ordered by numeric id, matching TinyDB), preserving every
// other table (metadata and the other entity tables).
func writeTable(portalKey, table string, rows map[string]Doc) error {
	path := dbPath(portalKey)
	root := map[string]map[string]Doc{}
	if b, err := os.ReadFile(path); err == nil {
		if err := json.Unmarshal(b, &root); err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	if root == nil {
		root = map[string]map[string]Doc{}
	}

	ids := make([]string, 0, len(rows))
	for id := range rows {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool {
		ai, aerr := strconv.Atoi(ids[i])
		bi, berr := strconv.Atoi(ids[j])
		if aerr == nil && berr == nil {
			return ai < bi
		}
		return ids[i] < ids[j]
	})

	tbl := make(map[string]Doc, len(ids))
	for i, id := range ids {
		tbl[strconv.Itoa(i+1)] = rows[id]
	}
	root[table] = tbl

	b, err := json.MarshalIndent(root, "", "  ")
	if err != nil {
		return err
	}
	return writeFile(path, b)
}
