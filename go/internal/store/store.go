// Package store handles on-disk locations and JSON/Markdown I/O, matching the
// Python layout: data/<portal>/<type>s/<id>.json and
// csbmdvault/<portal>/<type>s/<name>.md.
package store

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"

	"csb/internal/model"
	"csb/internal/textutil"
)

// ErrNotStored means the item has no stored data yet (i.e. it hasn't been
// fetched), so no Markdown path can be resolved for it.
var ErrNotStored = errors.New("item not stored")

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

// MarkdownPathForID resolves the absolute vault .md path for a stored item
// (table is paths/courses/labs). It returns ErrNotStored when the item hasn't
// been fetched yet. It does NOT check that the .md file exists on disk — an item
// fetched with --no-md has a valid path but no file — so the caller decides
// what a missing file means.
func MarkdownPathForID(portalKey, table, id string) (string, error) {
	var title string
	switch table {
	case "courses":
		c, err := LoadCourse(portalKey, id)
		if err != nil {
			return "", err
		}
		if c != nil {
			title = c.Title
		}
	case "paths":
		p, err := LoadPath(portalKey, id)
		if err != nil {
			return "", err
		}
		if p != nil {
			title = p.Title
		}
	case "labs":
		l, err := LoadLab(portalKey, id)
		if err != nil {
			return "", err
		}
		if l != nil {
			title = l.Title
		}
	default:
		return "", errors.New("unknown table: " + table)
	}
	if title == "" {
		return "", ErrNotStored
	}
	p := mdPath(portalKey, table, title)
	if abs, err := filepath.Abs(p); err == nil {
		return abs, nil
	}
	return p, nil
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
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return writeFile(path, append(b, '\n'))
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
	return path, writeFile(path, []byte(content))
}

// writeFile atomically writes bytes to path: it writes to a temp file in the
// same directory, fsyncs it, then renames it over the target. The rename is
// atomic on POSIX, so an interrupt (Ctrl+C) or crash can never leave a
// half-written database.json or per-item JSON backup — the file always holds
// either its previous contents or the complete new contents. Parent
// directories are created as needed.
func writeFile(path string, b []byte) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName) // no-op once the rename succeeds
	if _, err := tmp.Write(b); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	// CreateTemp makes 0600 files; match the 0644 the app wrote before.
	if err := os.Chmod(tmpName, 0o644); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}
