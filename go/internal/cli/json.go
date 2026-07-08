package cli

import (
	"encoding/json"
	"os"
	"strings"
	"time"

	"csb/internal/store"
)

// jsonItem is a structured list/search row for GUI/scripting consumers.
type jsonItem struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Type   string `json:"type"`
	Portal string `json:"portal"`
	// Fetch status, derived from the per-item JSON backup.
	Fetched     bool   `json:"fetched"`
	ScrapedTime int64  `json:"scrapedTime,omitempty"` // epoch ms, 0 if unknown
	ScrapedDate string `json:"scrapedDate,omitempty"` // local YYYY-MM-DD
}

// newJSONItem builds a list/search row, enriching it with fetch status read from
// the on-disk per-item JSON. table is the plural form (paths/courses/labs).
func newJSONItem(portalKey, table, id, name string) jsonItem {
	ms, fetched := store.FetchStatus(portalKey, table, id)
	it := jsonItem{
		ID:      id,
		Name:    name,
		Type:    strings.TrimSuffix(table, "s"),
		Portal:  portalKey,
		Fetched: fetched,
	}
	if fetched && ms > 0 {
		it.ScrapedTime = ms
		it.ScrapedDate = time.UnixMilli(ms).Format("2006-01-02")
	}
	return it
}

// fetchStatusText renders a compact, colorized fetch-status suffix for the plain
// (non-JSON) CLI listings: a green check + date when fetched, a dim dash when not.
func fetchStatusText(portalKey, table, id string) string {
	ms, fetched := store.FetchStatus(portalKey, table, id)
	if !fetched {
		return "\033[2m— not fetched\033[0m"
	}
	if ms > 0 {
		return "\033[32m✓ " + time.UnixMilli(ms).Format("2006-01-02") + "\033[0m"
	}
	return "\033[32m✓ fetched\033[0m"
}

// emitJSON writes v as indented JSON to stdout (the machine-readable channel).
func emitJSON(v any) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(v)
}
