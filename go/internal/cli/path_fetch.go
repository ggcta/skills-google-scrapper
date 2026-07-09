package cli

import (
	"fmt"
	"strings"
	"time"

	"csb/internal/browser"
	"csb/internal/mdgen"
	"csb/internal/portal"
	"csb/internal/scrape"
	"csb/internal/store"
)

// fetchPath ports the path branch of cmd_fetch: fetch the path, then cascade to
// every course (which fetches its own labs) and standalone lab in the plan,
// inheriting the flags and portal.
func fetchPath(sess *browser.Session, portalKey, id string, force, noMD, tocOnly, noTranscript bool) error {
	pathURL := portal.Get(portalKey).Paths + "/" + id
	fmt.Printf("Processing Path %s...\n", id)
	html, finalURL, err := sess.Navigate(pathURL, 1500*time.Millisecond)
	if err != nil {
		return err
	}
	if strings.Contains(finalURL, "sign_in") {
		return fmt.Errorf("authentication required — run 'skills-scraper login%s' first", portalFlagHint(portalKey))
	}

	pc, err := scrape.ParsePathHTML(html, portalKey)
	if err != nil {
		return err
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
	fmt.Printf("Path %s updated.\n", id)

	// Cascade down the tree.
	for _, key := range path.Courses.Keys {
		ref := path.Courses.Values[key]
		aType := strings.ToLower(ref.Type)
		if strings.Contains(aType, "lab") {
			fmt.Printf("\n--- Path %s > Lab %s - %s [%s] ---\n", id, ref.ID, ref.Name, portalKey)
			// Partner labs live at a parent-referencing focus URL (ref.URL).
			if err := fetchLab(sess, portalKey, ref.ID, ref.URL, force, noMD, tocOnly); err != nil {
				fmt.Printf("Failed to fetch lab %s in path %s: %v\n", ref.ID, id, err)
			}
			continue
		}
		fmt.Printf("\n--- Path %s > Course %s - %s [%s] ---\n", id, ref.ID, ref.Name, portalKey)
		_ = store.UpsertCollectionName(portalKey, "courses", ref.ID, ref.Name)
		if err := fetchCourse(sess, portalKey, ref.ID, force, noMD, tocOnly, noTranscript); err != nil {
			fmt.Printf("Failed to fetch course %s in path %s: %v\n", ref.ID, id, err)
		}
	}
	return nil
}
