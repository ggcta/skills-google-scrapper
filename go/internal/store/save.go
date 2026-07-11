package store

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"time"

	"csb/internal/model"
	"csb/internal/portal"
)

// NowMillis is the current epoch in milliseconds (matches Python scrapedTime).
func NowMillis() int64 { return time.Now().UnixMilli() }

// labDisk is the on-disk lab document, with fields ordered to match the Python
// to_dict output so re-fetches don't churn the JSON key order.
type labDisk struct {
	ID          string                   `json:"id"`
	Title       string                   `json:"title"`
	Description string                   `json:"description"`
	Portal      string                   `json:"portal"`
	Steps       model.OrderedMap[string] `json:"steps"`
	Type        string                   `json:"type"`
	URL         string                   `json:"url"`
	ScrapedTime int64                    `json:"scrapedTime"`
}

// SaveLabEntity stamps scrapedTime, writes the per-item JSON, and upserts the
// lab into the database (labs table) so list/search reflect it. It mutates
// lab.ScrapedTime so the caller can generate Markdown with the same timestamp.
func SaveLabEntity(lab *model.Lab) error {
	if lab.Portal == "" {
		lab.Portal = portal.Default
	}
	lab.ScrapedTime = NowMillis()

	disk := labDisk{
		ID:          lab.ID.String(),
		Title:       lab.Title,
		Description: lab.Description,
		Portal:      lab.PortalKey(),
		Steps:       lab.Steps,
		Type:        "Lab",
		URL:         lab.URL(),
		ScrapedTime: lab.ScrapedTime,
	}
	b, err := json.MarshalIndent(disk, "", "  ")
	if err != nil {
		return err
	}
	if err := writeFile(jsonPath(lab.PortalKey(), "labs", lab.ID.String()), append(b, '\n')); err != nil {
		return err
	}

	// Compact ledger row (backlog #9): the full data lives in the per-item JSON
	// above; the DB is only an index for the catalog + list/search + last-known
	// status. scrapedTime is carried so the ledger retains status even if the
	// per-item file is later deleted. Kept in step with Python's _ledger_row.
	return UpsertDoc(lab.PortalKey(), "labs", map[string]any{
		"id":          lab.ID.String(),
		"title":       lab.Title,
		"name":        lab.Title,
		"type":        "Lab",
		"portal":      lab.PortalKey(),
		"scrapedTime": lab.ScrapedTime,
	})
}

// UpsertDoc merges doc into a TinyDB table by matching the "id" field, or inserts
// it under the next integer key. Preserves other tables (e.g. metadata). The
// output is valid TinyDB JSON that the Python tool reads without issue.
func UpsertDoc(portalKey, table string, doc map[string]any) error {
	path := dbPath(portalKey)
	root := map[string]map[string]map[string]any{}
	if b, err := os.ReadFile(path); err == nil {
		if err := json.Unmarshal(b, &root); err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	if root == nil {
		root = map[string]map[string]map[string]any{}
	}
	tbl := root[table]
	if tbl == nil {
		tbl = map[string]map[string]any{}
		root[table] = tbl
	}

	id := fmt.Sprint(doc["id"])
	foundKey := ""
	maxKey := 0
	for k, d := range tbl {
		if n, err := strconv.Atoi(k); err == nil && n > maxKey {
			maxKey = n
		}
		if fmt.Sprint(d["id"]) == id {
			foundKey = k
		}
	}
	if foundKey != "" {
		for k, v := range doc { // merge
			tbl[foundKey][k] = v
		}
	} else {
		tbl[strconv.Itoa(maxKey+1)] = doc
	}

	b, err := json.MarshalIndent(root, "", "  ")
	if err != nil {
		return err
	}
	return writeFile(path, b)
}
