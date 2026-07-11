package cli

import (
	"strings"

	"csb/internal/store"
)

// Completeness checks (backlog #6): decide locally — WITHOUT touching the
// browser — whether an item has already been fully fetched, so fetch can skip it
// and avoid launching Chrome (#7) unless --force is given (#8). The signal is the
// stored JSON existing AND carrying a non-zero scrapedTime (with a title/name),
// which every save stamps; a fetch interrupted before an item was saved leaves no
// scrapedTime, so it is correctly seen as incomplete.

// labComplete reports whether the lab's JSON is present and fully scraped.
// scrapedTime is stamped only on a successful (atomic) save, so a non-zero value
// alone proves a complete record exists; the title is not required (some valid
// records carry an empty title).
func labComplete(portalKey, id string) bool {
	lab, _ := store.LoadLab(portalKey, id)
	return lab != nil && lab.ScrapedTime > 0
}

// courseComplete reports whether the course's JSON is present and fully scraped.
func courseComplete(portalKey, id string) bool {
	c, _ := store.LoadCourse(portalKey, id)
	return c != nil && c.ScrapedTime > 0
}

// pathComplete reports whether the path AND its whole cascade are done: the path's
// own JSON must be fully scraped, and every direct child it lists (each course or
// lab in path.Courses) must itself be complete. This is the "deep" check that lets
// an interrupted cascade (path saved but not all of its courses/labs) resume.
//
// The descent stops one level down: a child course is judged by its own JSON, not
// re-descended into that course's embedded labs — a course's lab activities are
// keyed by activity id, which need not equal the lab entity's stored id (see
// processCourseLab / ParseLabReviewID), so descending further risks false
// negatives. Checking a path's direct children already catches the real
// interruption case.
func pathComplete(portalKey, id string) bool {
	p, _ := store.LoadPath(portalKey, id)
	if p == nil || p.ScrapedTime <= 0 {
		return false
	}
	for _, key := range p.Courses.Keys {
		ref := p.Courses.Values[key]
		if strings.Contains(strings.ToLower(ref.Type), "lab") {
			if !labComplete(portalKey, ref.ID) {
				return false
			}
			continue
		}
		if !courseComplete(portalKey, ref.ID) {
			return false
		}
	}
	return true
}

// itemComplete dispatches the completeness check by kind (singular or plural), so
// the fetch launch gate can decide whether the browser is needed at all.
func itemComplete(portalKey, kind, id string) bool {
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case "path", "paths":
		return pathComplete(portalKey, id)
	case "course", "courses":
		return courseComplete(portalKey, id)
	case "lab", "labs":
		return labComplete(portalKey, id)
	default:
		return false
	}
}
