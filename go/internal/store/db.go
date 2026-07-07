package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
)

// dbPath is the per-portal TinyDB file.
func dbPath(portalKey string) string {
	return filepath.Join(DataRoot(), portalKey, "database.json")
}

// Doc is a single database document (a decoded JSON object).
type Doc map[string]any

// LoadTable returns all documents in a TinyDB table (paths/courses/labs),
// ordered by numeric document key to mirror TinyDB's table.all() ordering.
// Returns an empty slice if the database or table is absent.
func LoadTable(portalKey, table string) ([]Doc, error) {
	b, err := os.ReadFile(dbPath(portalKey))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	// database.json is { "<table>": { "<docId>": {..fields..}, ... }, ... }
	var root map[string]map[string]Doc
	if err := json.Unmarshal(b, &root); err != nil {
		return nil, err
	}
	tbl, ok := root[table]
	if !ok {
		return nil, nil
	}
	keys := make([]string, 0, len(tbl))
	for k := range tbl {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		ai, aerr := strconv.Atoi(keys[i])
		bi, berr := strconv.Atoi(keys[j])
		if aerr == nil && berr == nil {
			return ai < bi
		}
		return keys[i] < keys[j]
	})
	docs := make([]Doc, 0, len(keys))
	for _, k := range keys {
		docs = append(docs, tbl[k])
	}
	return docs, nil
}

// Name returns a document's display name, preferring "name" then "title",
// matching the Python collection fallback.
func (d Doc) Name() string {
	if v, ok := d["name"].(string); ok && v != "" {
		return v
	}
	if v, ok := d["title"].(string); ok && v != "" {
		return v
	}
	return ""
}

// ID returns a document's id as a string.
func (d Doc) ID() string {
	switch v := d["id"].(type) {
	case string:
		return v
	case float64:
		return strconv.FormatFloat(v, 'f', -1, 64)
	default:
		return ""
	}
}
