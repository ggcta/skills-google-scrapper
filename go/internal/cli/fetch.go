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

// cmdFetch scrapes content into Markdown + JSON. This slice implements standalone
// lab fetching (-l) end-to-end; course (-c) and path (-p) fetching land in the
// next slice (they require the deep per-activity extraction pipeline).
func cmdFetch(args []string) int {
	p := parseArgs(args, map[string]bool{
		"-c": true, "--courses": true,
		"-p": true, "--paths": true,
		"-l": true, "--labs": true,
	})
	force := p.has("--force", "-f")
	noMD := p.has("--no-md")
	tocOnly := p.has("--toc", "-t")
	headless := p.has("--headless")

	labIDs, hasL := p.value("-l", "--labs")
	_, hasC := p.value("-c", "--courses")
	_, hasP := p.value("-p", "--paths")

	if !hasL && !hasC && !hasP {
		fmt.Println("Please specify items to fetch using -p <id>, -c <id>, or -l <id>.")
		return 1
	}
	if hasC || hasP {
		fmt.Println("Note: course (-c) and path (-p) fetching are not in the Go build yet.")
		fmt.Println("      Use the Python CLI for those, or fetch labs with -l. (Coming next.)")
		if !hasL {
			return 1
		}
	}

	// --- Labs ---
	ids := splitIDs(labIDs)
	fmt.Printf("\n--- Processing Labs: %v ---\n", ids)
	fmt.Println("\nLaunching browser for lab extraction...")
	sess, err := browser.Launch(context.Background(), browser.Options{
		ProfileDir: browser.DefaultProfileDir(),
		Headless:   headless,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "error launching browser: %v\n", err)
		return 1
	}
	defer sess.Close()

	rc := 0
	for _, raw := range ids {
		pk, id := portal.AndID(raw)
		if pk == "" {
			pk = p.portal
		}
		if err := fetchLab(sess, pk, id, force, noMD, tocOnly); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to fetch lab %s: %v\n", id, err)
			rc = 1
		}
	}
	return rc
}

// fetchLab loads, parses, and persists a single lab (JSON + Markdown + DB).
func fetchLab(sess *browser.Session, portalKey, id string, force, noMD, tocOnly bool) error {
	// Skip if already stored, unless forced (mirrors Lab.fetch_data).
	if !force {
		if existing, _ := store.LoadLab(portalKey, id); existing != nil && existing.Title != "" {
			fmt.Printf("•-• [+] Existed: %s - %s\n", id, existing.Title)
			return nil
		}
	}

	target := portal.Get(portalKey).Lab + "/" + id // catalog_lab/<id>
	fmt.Printf("Fetching: %s\n", target)
	html, finalURL, err := sess.Navigate(target, 1500*time.Millisecond)
	if err != nil {
		return err
	}
	if strings.Contains(finalURL, "sign_in") {
		return fmt.Errorf("authentication required — run 'csb login%s' first",
			portalFlagHint(portalKey))
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
