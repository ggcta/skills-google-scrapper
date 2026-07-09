package cli

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"csb/internal/browser"
	"csb/internal/mdgen"
	"csb/internal/portal"
	"csb/internal/scrape"
	"csb/internal/store"
)

// cmdFetch scrapes content into Markdown + JSON: paths cascade to their courses
// and labs; courses cascade to their labs; flags and portal inherit down the
// tree. Ports the Python cmd_fetch.
func cmdFetch(args []string) int {
	p := parseArgs(args, map[string]bool{
		"-c": true, "--courses": true,
		"-p": true, "--paths": true,
		"-l": true, "--labs": true,
	})
	force := p.has("--force", "-f")
	noMD := p.has("--no-md")
	tocOnly := p.has("--toc", "-t")
	noTranscript := p.has("--no-transcript")
	headless := p.has("--headless")

	pathIDs, hasP := p.value("-p", "--paths")
	courseIDs, hasC := p.value("-c", "--courses")
	labIDs, hasL := p.value("-l", "--labs")
	all := p.has("--all")

	if !hasP && !hasC && !hasL && !all {
		fmt.Println("Please specify items to fetch using -p <id>, -c <id>, or -l <id>.")
		return 1
	}

	// Resolve/validate the bulk-mode kind up front, before spending a browser.
	allKind := "paths"
	if all {
		if len(p.positionals) > 0 {
			allKind = p.positionals[0]
		}
		if kindTables(allKind) == nil {
			fmt.Fprintf(os.Stderr, "Unknown kind %q for --all (use paths, courses, labs, or all).\n", allKind)
			return 1
		}
	}

	fmt.Println("\nLaunching browser...")
	sess, err := browser.Launch(context.Background(), browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   headless,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "error launching browser: %v\n", err)
		return 1
	}
	defer sess.Close()

	// Hidden bulk mode: `fetch --all [paths|courses|labs|all]` refreshes the
	// catalog(s) from the site then fetches every item. Default kind is paths
	// (which cascade to their courses and labs).
	if all {
		return fetchAll(sess, p.portal, allKind, force, noMD, tocOnly, noTranscript)
	}

	rc := 0
	// Paths first (cascade), then standalone courses, then standalone labs.
	for _, raw := range splitIDs(pathIDs) {
		pk, id := resolvePortal(raw, p.portal)
		fmt.Printf("\n--- Processing Path %s [%s] ---\n", id, pk)
		if err := fetchPath(sess, pk, id, force, noMD, tocOnly, noTranscript); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to fetch path %s: %v\n", id, err)
			rc = 1
		}
	}
	for _, raw := range splitIDs(courseIDs) {
		pk, id := resolvePortal(raw, p.portal)
		fmt.Printf("\n--- Processing Course %s [%s] ---\n", id, pk)
		if err := fetchCourse(sess, pk, id, force, noMD, tocOnly, noTranscript); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to fetch course %s: %v\n", id, err)
			rc = 1
		}
	}
	for _, raw := range splitIDs(labIDs) {
		pk, id := resolvePortal(raw, p.portal)
		fmt.Printf("\n--- Processing Lab %s [%s] ---\n", id, pk)
		if err := fetchLab(sess, pk, id, "", force, noMD, tocOnly); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to fetch lab %s: %v\n", id, err)
			rc = 1
		}
	}
	return rc
}

// fetchAll refreshes the relevant catalog(s) from the site, then fetches every
// stored item. kind is one of paths/courses/labs (singular accepted) or "all".
// Paths cascade to their courses and labs, so `fetch --all` (kind=paths) already
// pulls almost everything; "all" additionally sweeps standalone courses/labs.
func fetchAll(sess *browser.Session, portalKey, kind string, force, noMD, tocOnly, noTranscript bool) int {
	tables := kindTables(kind)
	if tables == nil {
		fmt.Fprintf(os.Stderr, "Unknown kind %q for --all (use paths, courses, labs, or all).\n", kind)
		return 1
	}

	rc := 0
	for _, table := range tables {
		fmt.Printf("\n=== Fetching ALL %s [%s] ===\n", table, portalKey)
		if err := reloadListWith(sess, portalKey, table); err != nil {
			// Non-fatal: fall back to whatever is already stored locally.
			fmt.Fprintf(os.Stderr, "warning: could not refresh %s catalog: %v\n", table, err)
		}
		docs, err := store.LoadTable(portalKey, table)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error loading %s: %v\n", table, err)
			rc = 1
			continue
		}
		if len(docs) == 0 {
			fmt.Printf("No %s found for [%s].\n", table, portalKey)
			continue
		}
		singular := map[string]string{"paths": "Path", "courses": "Course", "labs": "Lab"}[table]
		for i, d := range docs {
			id := d.ID()
			if id == "" {
				continue
			}
			fmt.Printf("\n--- [%d/%d] %s %s [%s] ---\n", i+1, len(docs), singular, id, portalKey)
			var e error
			switch table {
			case "paths":
				e = fetchPath(sess, portalKey, id, force, noMD, tocOnly, noTranscript)
			case "courses":
				e = fetchCourse(sess, portalKey, id, force, noMD, tocOnly, noTranscript)
			case "labs":
				e = fetchLab(sess, portalKey, id, "", force, noMD, tocOnly)
			}
			if e != nil {
				fmt.Fprintf(os.Stderr, "Failed to fetch %s %s: %v\n", singular, id, e)
				rc = 1
			}
		}
	}
	return rc
}

// kindTables maps a --all kind argument to the catalog tables to sweep.
func kindTables(kind string) []string {
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case "", "path", "paths", "p":
		return []string{"paths"}
	case "course", "courses", "c":
		return []string{"courses"}
	case "lab", "labs", "l":
		return []string{"labs"}
	case "all", "everything", "*":
		return []string{"paths", "courses", "labs"}
	default:
		return nil
	}
}

// resolvePortal resolves a raw id/URL into (portal, id); a URL host overrides the
// default portal.
func resolvePortal(raw, defaultPortal string) (string, string) {
	pk, id := portal.AndID(raw)
	if pk == "" {
		pk = defaultPortal
	}
	return pk, id
}

// fetchLab loads, parses, and persists a single lab. When fetchURL is empty the
// lab's catalog URL is used; partner labs from a path pass their focus URL.
func fetchLab(sess *browser.Session, portalKey, id, fetchURL string, force, noMD, tocOnly bool) error {
	if !force {
		if existing, _ := store.LoadLab(portalKey, id); existing != nil && existing.Title != "" {
			fmt.Printf("•-• [+] Existed: %s - %s\n", id, existing.Title)
			return nil
		}
	}

	target := fetchURL
	if target == "" {
		target = portal.Get(portalKey).Lab + "/" + id // catalog_lab/<id>
	}
	fmt.Printf("Fetching: %s\n", target)
	html, finalURL, err := sess.Navigate(target, 1500*time.Millisecond)
	if err != nil {
		return err
	}
	if strings.Contains(finalURL, "sign_in") {
		return fmt.Errorf("authentication required — run 'skills-scraper login%s' first", portalFlagHint(portalKey))
	}

	lc, err := scrape.ParseLabHTML(html)
	if err != nil {
		return err
	}
	if lc.Name == "" {
		return fmt.Errorf("could not determine lab name (page may require sign-in)")
	}

	lab := lc.ToModel(id, portalKey)
	if err := store.SaveLabEntity(lab); err != nil {
		return err
	}
	if !noMD {
		if _, err := store.WriteLabMarkdown(lab, mdgen.Lab(lab, mdgen.Options{TOCOnly: tocOnly})); err != nil {
			return err
		}
	}
	fmt.Printf("•-• [+] %s - %s (%d steps)\n", id, lab.Title, lab.Steps.Len())
	return nil
}

func portalFlagHint(portalKey string) string {
	if portalKey == "partner" {
		return " -B"
	}
	return ""
}
