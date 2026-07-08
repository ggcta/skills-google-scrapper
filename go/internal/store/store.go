// Package store handles on-disk locations and JSON/Markdown I/O, matching the
// Python layout: data/<portal>/<type>s/<id>.json and
// csbmdvault/<portal>/<type>s/<name>.md.
package store

import (
	"encoding/json"
	"os"
	"path/filepath"

	"csb/internal/model"
	"csb/internal/textutil"
)

// DataRoot is the JSON/database root (override with CSB_DATA).
func DataRoot() string {
	if v := os.Getenv("CSB_DATA"); v != "" {
		return v
	}
	return "data"
}

// VaultRoot is the Markdown output root (override with CSB_VAULT).
func VaultRoot() string {
	if v := os.Getenv("CSB_VAULT"); v != "" {
		return v
	}
	return "csbmdvault"
}

func jsonPath(portalKey, typePlural, id string) string {
	return filepath.Join(DataRoot(), portalKey, typePlural, id+".json")
}

func mdPath(portalKey, typePlural, title string) string {
	name := textutil.ReplaceSpecialChars(title) + ".md"
	return filepath.Join(VaultRoot(), portalKey, typePlural, name)
}

func loadJSON(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, v)
}

// FetchStatus reports whether an item (table is paths/courses/labs) has been
// fully fetched and, if so, its scrapedTime in epoch-ms. The per-item JSON
// backup exists only after a real fetch — a catalog reload writes DB stubs only
// — so its presence is the source of truth for "downloaded". A present file
// with a zero/absent scrapedTime still counts as fetched (ms == 0).
func FetchStatus(portalKey, table, id string) (scrapedMs int64, fetched bool) {
	var meta struct {
		ScrapedTime int64 `json:"scrapedTime"`
	}
	if err := loadJSON(jsonPath(portalKey, table, id), &meta); err != nil {
		return 0, false
	}
	return meta.ScrapedTime, true
}

// LoadCourse reads a stored course. Returns (nil, nil) if the file is absent.
func LoadCourse(portalKey, id string) (*model.Course, error) {
	var c model.Course
	if err := loadJSON(jsonPath(portalKey, "courses", id), &c); err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	if c.Portal == "" {
		c.Portal = portalKey
	}
	return &c, nil
}

// LoadPath reads a stored path. Returns (nil, nil) if the file is absent.
func LoadPath(portalKey, id string) (*model.Path, error) {
	var p model.Path
	if err := loadJSON(jsonPath(portalKey, "paths", id), &p); err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	if p.Portal == "" {
		p.Portal = portalKey
	}
	return &p, nil
}

// LoadLab reads a stored lab. Returns (nil, nil) if the file is absent.
func LoadLab(portalKey, id string) (*model.Lab, error) {
	var l model.Lab
	if err := loadJSON(jsonPath(portalKey, "labs", id), &l); err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	if l.Portal == "" {
		l.Portal = portalKey
	}
	return &l, nil
}

// SaveCourse writes the course JSON backup.
func SaveCourse(c *model.Course) error { return saveJSON(jsonPath(c.PortalKey(), "courses", c.ID.String()), c) }

// SavePath writes the path JSON backup.
func SavePath(p *model.Path) error { return saveJSON(jsonPath(p.PortalKey(), "paths", p.ID.String()), p) }

// SaveLab writes the lab JSON backup.
func SaveLab(l *model.Lab) error { return saveJSON(jsonPath(l.PortalKey(), "labs", l.ID.String()), l) }

func saveJSON(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}

// WriteCourseMarkdown / WritePathMarkdown / WriteLabMarkdown write .md to the vault.
func WriteCourseMarkdown(c *model.Course, content string) (string, error) {
	return writeMD(mdPath(c.PortalKey(), "courses", c.Title), content)
}
func WritePathMarkdown(p *model.Path, content string) (string, error) {
	return writeMD(mdPath(p.PortalKey(), "paths", p.Title), content)
}
func WriteLabMarkdown(l *model.Lab, content string) (string, error) {
	return writeMD(mdPath(l.PortalKey(), "labs", l.Title), content)
}

func writeMD(path, content string) (string, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	return path, os.WriteFile(path, []byte(content), 0o644)
}

// writeFile writes bytes to path, creating parent directories.
func writeFile(path string, b []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}
