package store

import (
	"encoding/json"

	"csb/internal/model"
	"csb/internal/portal"
)

// courseDisk is the on-disk course document, fields ordered to match a fresh
// Python to_dict save (id, title, description, portal, datePublished,
// objectives, topics, modules, type, url, scrapedTime).
type courseDisk struct {
	ID            string         `json:"id"`
	Title         string         `json:"title"`
	Description   string         `json:"description"`
	Portal        string         `json:"portal"`
	DatePublished string         `json:"datePublished"`
	Objectives    []string       `json:"objectives"`
	Topics        []string       `json:"topics"`
	Modules       []model.Module `json:"modules"`
	Type          string         `json:"type"`
	URL           string         `json:"url"`
	ScrapedTime   int64          `json:"scrapedTime"`
}

// SaveCourseEntity stamps scrapedTime, writes the per-item JSON, and upserts
// course metadata into the database (courses table). Full modules are NOT
// embedded in the DB (to avoid bloat); UpsertDoc merges, so any modules a prior
// Python run stored are preserved.
func SaveCourseEntity(c *model.Course) error {
	if c.Portal == "" {
		c.Portal = portal.Default
	}
	c.ScrapedTime = NowMillis()

	disk := courseDisk{
		ID:            c.ID.String(),
		Title:         c.Title,
		Description:   c.Description,
		Portal:        c.PortalKey(),
		DatePublished: derefStr(c.DatePublished),
		Objectives:    nonNilSlice(c.Objectives),
		Topics:        derefSlice(c.Topics),
		Modules:       c.Modules,
		Type:          "Course",
		URL:           c.URL(),
		ScrapedTime:   c.ScrapedTime,
	}
	b, err := json.MarshalIndent(disk, "", "  ")
	if err != nil {
		return err
	}
	if err := writeFile(jsonPath(c.PortalKey(), "courses", c.ID.String()), append(b, '\n')); err != nil {
		return err
	}

	return UpsertDoc(c.PortalKey(), "courses", map[string]any{
		"id":            c.ID.String(),
		"title":         c.Title,
		"name":          c.Title,
		"description":   c.Description,
		"datePublished": derefStr(c.DatePublished),
		"topics":        derefSlice(c.Topics),
		"type":          "Course",
		"portal":        c.PortalKey(),
		"url":           c.URL(),
	})
}

// pathDisk is the on-disk path document in Python field order.
type pathDisk struct {
	ID            string                          `json:"id"`
	Title         string                          `json:"title"`
	Description   string                          `json:"description"`
	Portal        string                          `json:"portal"`
	DatePublished string                          `json:"datePublished"`
	Courses       model.OrderedMap[model.CourseRef] `json:"courses"`
	Type          string                          `json:"type"`
	URL           string                          `json:"url"`
	ScrapedTime   int64                           `json:"scrapedTime"`
}

// SavePathEntity writes the per-item JSON and upserts path metadata into the DB.
func SavePathEntity(p *model.Path) error {
	if p.Portal == "" {
		p.Portal = portal.Default
	}
	p.ScrapedTime = NowMillis()

	disk := pathDisk{
		ID:            p.ID.String(),
		Title:         p.Title,
		Description:   p.Description,
		Portal:        p.PortalKey(),
		DatePublished: derefStr(p.DatePublished),
		Courses:       p.Courses,
		Type:          "Path",
		URL:           p.URL(),
		ScrapedTime:   p.ScrapedTime,
	}
	b, err := json.MarshalIndent(disk, "", "  ")
	if err != nil {
		return err
	}
	if err := writeFile(jsonPath(p.PortalKey(), "paths", p.ID.String()), append(b, '\n')); err != nil {
		return err
	}

	return UpsertDoc(p.PortalKey(), "paths", map[string]any{
		"id":     p.ID.String(),
		"title":  p.Title,
		"name":   p.Title,
		"type":   "Path",
		"portal": p.PortalKey(),
		"url":    p.URL(),
	})
}

// UpsertCollectionName upserts just an id/name into a table (mirrors the Python
// Collection.save_json), used when a path discovers course/lab names.
func UpsertCollectionName(portalKey, table, id, name string) error {
	return UpsertDoc(portalKey, table, map[string]any{
		"id":     id,
		"name":   name,
		"type":   table,
		"portal": portalKey,
	})
}

func derefStr(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func derefSlice(s *[]string) []string {
	if s == nil {
		return []string{}
	}
	return nonNilSlice(*s)
}

func nonNilSlice(s []string) []string {
	if s == nil {
		return []string{}
	}
	return s
}
