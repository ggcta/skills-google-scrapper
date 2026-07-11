package cli

import (
	"fmt"
	"os"

	"csb/internal/mdgen"
	"csb/internal/store"
)

// cmdMD regenerates Markdown from stored data (no browser).
func cmdMD(args []string) int {
	p := parseArgs(args, map[string]bool{
		"-c": true, "--course": true,
		"-p": true, "--path": true,
		"-l": true, "--lab": true,
	})
	opts := mdgen.Options{
		TOCOnly:      p.has("--toc", "-t"),
		NoTranscript: p.has("--md-no-transcript", "--no-transcript"),
	}

	courseIDs, hasC := p.value("-c", "--course")
	pathIDs, hasP := p.value("-p", "--path")
	labIDs, hasL := p.value("-l", "--lab")
	if !hasC && !hasP && !hasL {
		fmt.Println("Please specify at least one item type: --course, --path, or --lab.")
		return 1
	}

	rc := 0
	if hasC {
		for _, id := range splitIDs(courseIDs) {
			fmt.Printf("Generating markdown for Course %s [%s]...\n", id, p.portal)
			c, err := store.LoadCourse(p.portal, id)
			if err != nil {
				fmt.Fprintf(os.Stderr, "  error: %v\n", err)
				rc = 1
				continue
			}
			if c == nil || c.Title == "" {
				fmt.Printf("Course %s data not found. Please fetch/extract first.\n", id)
				continue
			}
			path, err := store.WriteCourseMarkdown(c, mdgen.Course(c, opts))
			if err != nil {
				fmt.Fprintf(os.Stderr, "  error: %v\n", err)
				rc = 1
				continue
			}
			fmt.Printf("Markdown saved to %s\n", path)
		}
	}
	if hasP {
		for _, id := range splitIDs(pathIDs) {
			fmt.Printf("Generating markdown for Path %s [%s]...\n", id, p.portal)
			pth, err := store.LoadPath(p.portal, id)
			if err != nil {
				fmt.Fprintf(os.Stderr, "  error: %v\n", err)
				rc = 1
				continue
			}
			if pth == nil || pth.Title == "" {
				fmt.Printf("Path %s data not found. Please fetch first.\n", id)
				continue
			}
			path, err := store.WritePathMarkdown(pth, mdgen.Path(pth, opts))
			if err != nil {
				fmt.Fprintf(os.Stderr, "  error: %v\n", err)
				rc = 1
				continue
			}
			fmt.Printf("Markdown saved to %s\n", path)
		}
	}
	if hasL {
		for _, id := range splitIDs(labIDs) {
			fmt.Printf("Generating markdown for Lab %s [%s]...\n", id, p.portal)
			lab, err := store.LoadLab(p.portal, id)
			if err != nil {
				fmt.Fprintf(os.Stderr, "  error: %v\n", err)
				rc = 1
				continue
			}
			if lab == nil || lab.Title == "" {
				fmt.Printf("Lab %s data not found.\n", id)
				continue
			}
			path, err := store.WriteLabMarkdown(lab, mdgen.Lab(lab, opts))
			if err != nil {
				fmt.Fprintf(os.Stderr, "  error: %v\n", err)
				rc = 1
				continue
			}
			fmt.Printf("Markdown saved to %s\n", path)
		}
	}
	return rc
}
