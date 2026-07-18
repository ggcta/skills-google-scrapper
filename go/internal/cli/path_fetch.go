package cli

import (
	"strings"
	"time"

	"csb/internal/browser"
	"csb/internal/logx"
	"csb/internal/mdgen"
	"csb/internal/model"
	"csb/internal/portal"
	"csb/internal/scrape"
	"csb/internal/store"
)

// fetchPath ports the path branch of cmd_fetch: fetch the path, then cascade to
// every course (which fetches its own labs) and standalone lab in the plan,
// inheriting the flags and portal.
func fetchPath(sess *browser.Session, portalKey, id string, force, noMD, tocOnly, noTranscript bool) error {
	// Skip before any navigation when the path and its whole cascade are already
	// done (backlog #6/#7); --force re-fetches (#8).
	if !force && pathComplete(portalKey, id) {
		logx.Printf("•-• [+] Path %s already complete.\n", labelFor(portalKey, "paths", id))
		return nil
	}
	pathURL := portal.Get(portalKey).Paths + "/" + id
	logx.Printf("Processing Path %s...\n", id)
	html, finalURL, err := sess.Navigate(pathURL, 1500*time.Millisecond)
	if err != nil {
		return err
	}
	html, err = ensureAuthenticated(sess, pathURL, html, finalURL, 1500*time.Millisecond, "path "+id)
	if err != nil {
		return err
	}

	pc, err := scrape.ParsePathHTML(html, portalKey)
	if err != nil {
		return err
	}
	if sess.ConnectionLost() {
		return browser.ErrConnectionLost
	}
	if sess.Interrupted() {
		return errInterrupted
	}
	path := pc.ToModel(id, portalKey)
	if err := store.SavePathEntity(path); err != nil {
		return err
	}
	if !noMD {
		if _, err := store.WritePathMarkdown(path, mdgen.Path(path, mdgen.Options{TOCOnly: tocOnly})); err != nil {
			return err
		}
	}
	itemSaved("path", portalKey, id, path.Title, path.ScrapedTime)
	logx.Printf("Path %s updated.\n", id)

	// Cascade down the tree, capturing any resolved ids. Partner path activities
	// are session deep-links with no catalog id (e.g. .../course_sessions/.../
	// video/450874); fetchCourse/fetchLab resolve the real id (32) from the target
	// page's canonical URL and return it, so the stored path can be corrected.
	corrected := make([]model.CourseRef, 0, len(path.Courses.Keys))
	changed := false
	for _, key := range path.Courses.Keys {
		if stopRequested(sess) {
			return errInterrupted
		}
		ref := path.Courses.Values[key]
		aType := strings.ToLower(ref.Type)
		if strings.Contains(aType, "lab") {
			logx.Printf("\nPath %s > Lab %s - %s [%s]\n", id, ref.ID, ref.Name, portalKey)
			// Partner labs live at a parent-referencing focus URL (ref.URL).
			realID, err := fetchLab(sess, portalKey, ref.ID, ref.URL, force, noMD, tocOnly)
			if reportable(sess, err) {
				logx.Errf("Failed to fetch lab %s in path %s: %v\n", ref.ID, id, err)
			}
			corrected = append(corrected, correctRef(ref, realID, portalKey, &changed))
			continue
		}
		logx.Printf("\nPath %s > Course %s - %s [%s]\n", id, ref.ID, ref.Name, portalKey)
		realID, err := fetchCourse(sess, portalKey, ref.ID, ref.URL, force, noMD, tocOnly, noTranscript)
		if reportable(sess, err) {
			logx.Errf("Failed to fetch course %s in path %s: %v\n", ref.ID, id, err)
		}
		cref := correctRef(ref, realID, portalKey, &changed)
		_ = store.UpsertCollectionName(portalKey, "courses", cref.ID, cref.Name)
		corrected = append(corrected, cref)
	}

	// If any activity resolved to a different (real) catalog id, rewrite the
	// stored path so its json/markdown reference the correct ids from now on.
	if changed {
		var oc model.OrderedMap[model.CourseRef]
		for _, c := range corrected {
			oc.Set(c.ID, c)
		}
		path.Courses = oc
		if err := store.SavePathEntity(path); err != nil {
			return err
		}
		if !noMD {
			if _, err := store.WritePathMarkdown(path, mdgen.Path(path, mdgen.Options{TOCOnly: tocOnly})); err != nil {
				return err
			}
		}
		logx.Printf("Path %s course/lab ids corrected to catalog ids.\n", id)
	}
	return nil
}

// correctRef returns ref with its id/URL rewritten to the resolved catalog id
// when the fetch resolved a partner session deep-link to a different real id,
// flagging that the path changed. Otherwise ref is returned unchanged.
func correctRef(ref model.CourseRef, realID, portalKey string, changed *bool) model.CourseRef {
	if realID == "" || realID == ref.ID {
		return ref
	}
	*changed = true
	out := ref
	out.ID = realID
	base := portal.Get(portalKey).Base
	if strings.Contains(strings.ToLower(ref.Type), "lab") {
		out.URL = base + "/catalog_lab/" + realID
	} else {
		out.URL = base + "/course_templates/" + realID
	}
	return out
}
