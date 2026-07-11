package cli

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"csb/internal/browser"
	"csb/internal/logx"
	"csb/internal/mdgen"
	"csb/internal/portal"
	"csb/internal/scrape"
	"csb/internal/store"
)

// errInterrupted is returned by a fetch when the user pressed Ctrl+C before the
// item could be fully scraped, so nothing partial is saved and the caller can
// stop the run quietly rather than reporting it as a failure.
var errInterrupted = errors.New("interrupted")

// emitProgress, set by the hidden --emit-progress flag, makes fetch print a
// machine-readable "@@ITEM {json}" line to stdout after each item is saved, so a
// wrapping GUI can refresh its view live. It stays off for normal CLI use, where
// the human-readable progress lines are enough.
var emitProgress bool

// itemSaved prints the structured per-item progress marker when --emit-progress
// is on. kind is the singular lowercase type (path/course/lab). It is called
// right after the item's JSON + DB row are persisted, so the fields it reports
// are already durable on disk.
func itemSaved(kind, portalKey, id, name string, scrapedMs int64) {
	if !emitProgress {
		return
	}
	date := ""
	if scrapedMs > 0 {
		date = time.UnixMilli(scrapedMs).Format("2006-01-02")
	}
	b, err := json.Marshal(map[string]any{
		"portal":      portalKey,
		"kind":        kind,
		"id":          id,
		"name":        name,
		"scrapedTime": scrapedMs,
		"scrapedDate": date,
	})
	if err == nil {
		// Raw (un-timestamped) so the GUI's "@@ITEM " line parser still matches.
		logx.Raw(fmt.Sprintf("@@ITEM %s\n", b))
	}
}

// reportable is true when err is a real failure worth printing — not nil, not an
// interrupt, and not an error produced while the run was being canceled (a
// canceled navigation surfaces as a generic error before the loop's next
// interrupt check).
func reportable(sess *browser.Session, err error) bool {
	return err != nil && !errors.Is(err, errInterrupted) && !sess.Interrupted()
}

// cmdFetch scrapes content into Markdown + JSON: paths cascade to their courses
// and labs; courses cascade to their labs; flags and portal inherit down the
// tree. Ports the Python cmd_fetch.
func cmdFetch(args []string) int {
	p := parseArgs(args, map[string]bool{
		"-c": true, "--courses": true,
		"-p": true, "--paths": true,
		"-l": true, "--labs": true,
		"--log-dir": true,
	})
	force := p.has("--force", "-f")
	noMD := p.has("--no-md")
	tocOnly := p.has("--toc", "-t")
	noTranscript := p.has("--no-transcript")
	headless := p.has("--headless")
	emitProgress = p.has("--emit-progress")

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

	// Start the activity log for this run: every fetch line below is timestamped
	// (ms precision) and mirrored to a per-run file under the log dir (default
	// ./logs, override with --log-dir or CSB_LOG_DIR).
	logDir, _ := p.value("--log-dir")
	if logDir == "" {
		logDir = logx.Dir()
	}
	if path, err := logx.Init(logDir); err != nil {
		fmt.Fprintf(os.Stderr, "warning: could not open log file in %s: %v\n", logDir, err)
	} else {
		fmt.Printf("Logging this run to %s\n", path)
	}
	defer logx.Close()

	// A Ctrl+C (or SIGTERM) cancels this context, which aborts any in-flight
	// browser navigation and lets the fetch loops stop cleanly between items.
	// Because every completed item is written atomically as it finishes, an
	// interrupt never corrupts the database or loses already-fetched items.
	ctx, stop := browserSignalContext()
	defer stop()

	logx.Println("\nLaunching browser...")
	sess, err := browser.Launch(ctx, browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   headless,
	})
	if err != nil {
		logx.Errf("error launching browser: %v\n", err)
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
		if sess.Interrupted() {
			break
		}
		pk, id := resolvePortal(raw, p.portal)
		logx.Printf("\nProcessing Path %s [%s]\n", labelFor(pk, "paths", id), pk)
		if err := fetchPath(sess, pk, id, force, noMD, tocOnly, noTranscript); reportable(sess, err) {
			logx.Errf("Failed to fetch path %s: %v\n", id, err)
			rc = 1
		}
	}
	for _, raw := range splitIDs(courseIDs) {
		if sess.Interrupted() {
			break
		}
		pk, id := resolvePortal(raw, p.portal)
		logx.Printf("\nProcessing Course %s [%s]\n", labelFor(pk, "courses", id), pk)
		if err := fetchCourse(sess, pk, id, force, noMD, tocOnly, noTranscript); reportable(sess, err) {
			logx.Errf("Failed to fetch course %s: %v\n", id, err)
			rc = 1
		}
	}
	for _, raw := range splitIDs(labIDs) {
		if sess.Interrupted() {
			break
		}
		pk, id := resolvePortal(raw, p.portal)
		logx.Printf("\nProcessing Lab %s [%s]\n", labelFor(pk, "labs", id), pk)
		if err := fetchLab(sess, pk, id, "", force, noMD, tocOnly); reportable(sess, err) {
			logx.Errf("Failed to fetch lab %s: %v\n", id, err)
			rc = 1
		}
	}
	if sess.Interrupted() {
		logx.Errf("\nInterrupted — stopped cleanly; completed items are saved.\n")
	}
	return rc
}

// labelFor renders an item as "<id> - <name>" when the name is known locally, or
// just "<id>" otherwise, so fetch progress lines are human-readable.
func labelFor(portalKey, table, id string) string {
	if name := store.LookupName(portalKey, table, id); name != "" {
		return id + " - " + name
	}
	return id
}

// fetchAll refreshes the relevant catalog(s) from the site, then fetches every
// stored item. kind is one of paths/courses/labs (singular accepted) or "all".
// Paths cascade to their courses and labs, so `fetch --all` (kind=paths) already
// pulls almost everything; "all" additionally sweeps standalone courses/labs.
func fetchAll(sess *browser.Session, portalKey, kind string, force, noMD, tocOnly, noTranscript bool) int {
	tables := kindTables(kind)
	if tables == nil {
		logx.Errf("Unknown kind %q for --all (use paths, courses, labs, or all).\n", kind)
		return 1
	}

	rc := 0
	for _, table := range tables {
		logx.Printf("\nFetching ALL %s [%s]\n", table, portalKey)
		if err := reloadListWith(sess, portalKey, table); err != nil {
			// Non-fatal: fall back to whatever is already stored locally.
			logx.Errf("warning: could not refresh %s catalog: %v\n", table, err)
		}
		docs, err := store.LoadTable(portalKey, table)
		if err != nil {
			logx.Errf("error loading %s: %v\n", table, err)
			rc = 1
			continue
		}
		if len(docs) == 0 {
			logx.Printf("No %s found for [%s].\n", table, portalKey)
			continue
		}
		singular := map[string]string{"paths": "Path", "courses": "Course", "labs": "Lab"}[table]
		for i, d := range docs {
			if sess.Interrupted() {
				break
			}
			id := d.ID()
			if id == "" {
				continue
			}
			label := id
			if name := d.Name(); name != "" {
				label = id + " - " + name
			}
			logx.Printf("\n[%d/%d] %s %s [%s]\n", i+1, len(docs), singular, label, portalKey)
			var e error
			switch table {
			case "paths":
				e = fetchPath(sess, portalKey, id, force, noMD, tocOnly, noTranscript)
			case "courses":
				e = fetchCourse(sess, portalKey, id, force, noMD, tocOnly, noTranscript)
			case "labs":
				e = fetchLab(sess, portalKey, id, "", force, noMD, tocOnly)
			}
			if reportable(sess, e) {
				logx.Errf("Failed to fetch %s %s: %v\n", singular, id, e)
				rc = 1
			}
		}
		if sess.Interrupted() {
			break
		}
	}
	if sess.Interrupted() {
		logx.Errf("\nInterrupted — stopped cleanly; completed items are saved.\n")
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
			logx.Printf("•-• [+] Existed: %s - %s\n", id, existing.Title)
			return nil
		}
	}

	target := fetchURL
	if target == "" {
		target = portal.Get(portalKey).Lab + "/" + id // catalog_lab/<id>
	}
	logx.Printf("Fetching: %s\n", target)
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

	if sess.Interrupted() {
		return errInterrupted
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
	itemSaved("lab", portalKey, id, lab.Title, lab.ScrapedTime)
	logx.Printf("•-• [+] %s - %s (%d steps)\n", id, lab.Title, lab.Steps.Len())
	return nil
}

func portalFlagHint(portalKey string) string {
	if portalKey == "partner" {
		return " -B"
	}
	return ""
}
