// Package mdgen ports the Python Markdown generators (BaseEntity front matter +
// Course/Path/Lab bodies) so output matches the reference vault byte-for-byte.
package mdgen

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"csb/internal/model"
	"csb/internal/textutil"
)

// Options mirror the toc_only / no_transcript flags.
type Options struct {
	TOCOnly      bool
	NoTranscript bool
}

// frontMatter builds the YAML front matter shared by all entities. Optional
// lines are emitted only when the corresponding source key was present:
//   - datePublished: pointer non-nil
//   - topics: pointer non-nil (bare "topics:" when the list is empty)
// portal is always emitted (defaults to public upstream).
func frontMatter(id, title, typ, portalKey, url string, datePublished *string, topics *[]string, scrapedTime int64) string {
	var b []string
	b = append(b, "---")
	b = append(b, fmt.Sprintf("id: '%s'", id))
	if title != "" {
		b = append(b, fmt.Sprintf("title: '%s'", title))
	}
	b = append(b, "type: "+typ)
	if portalKey != "" {
		b = append(b, "portal: "+portalKey)
	}
	b = append(b, "url: "+url)
	if datePublished != nil {
		b = append(b, "date_published: "+*datePublished)
	}
	if topics != nil {
		if len(*topics) > 0 {
			lines := make([]string, len(*topics))
			for i, t := range *topics {
				lines[i] = "  - " + t
			}
			b = append(b, "topics:\n"+strings.Join(lines, "\n"))
		} else {
			b = append(b, "topics:")
		}
	}
	b = append(b, "scraped_date: "+scrapedDate(scrapedTime))
	b = append(b, "---")
	return strings.Join(b, "\n")
}

// scrapedDate formats an epoch-ms timestamp as local YYYY-MM-DD, or today when
// unset — matching datetime.fromtimestamp in the Python version.
func scrapedDate(ms int64) string {
	if ms == 0 {
		return time.Now().Format("2006-01-02")
	}
	return time.UnixMilli(ms).Format("2006-01-02")
}

// Course renders a course to Markdown (ports Course.generate_markdown).
func Course(c *model.Course, opts Options) string {
	base := c.BaseURL()
	var md []string
	md = append(md, frontMatter(c.ID.String(), c.Title, "Course", c.PortalKey(), c.URL(), c.DatePublished, c.Topics, c.ScrapedTime))
	md = append(md, fmt.Sprintf("# [%s](%s)", c.Title, c.URL()))

	if !opts.TOCOnly {
		if c.Description != "" {
			md = append(md, "**Description:**")
			md = append(md, textutil.ReplaceQuoteMarks(c.Description))
		}
		if len(c.Objectives) > 0 {
			var objs []string
			for _, o := range c.Objectives {
				objs = append(objs, "* "+textutil.ReplaceQuoteMarks(o))
			}
			md = append(md, "**Objectives:**")
			md = append(md, strings.Join(objs, "\n"))
		}
	}

	for _, module := range c.Modules {
		md = append(md, "## "+strings.TrimSpace(module.Title))
		if !opts.TOCOnly && module.Description != "" {
			md = append(md, textutil.ReplaceQuoteMarks(textutil.CleanText(module.Description)))
		}
		for _, step := range module.Steps {
			for _, a := range step.Activities {
				title := strings.TrimSpace(a.Title)
				href := a.Href
				// Python uses base_url + (href or '') here, so an empty href
				// still yields the bare portal base URL in the heading link.
				link := base + href
				if a.Type == "html_bundle" {
					md = append(md, fmt.Sprintf("### HTML - [%s](%s)", title, link))
				} else {
					md = append(md, fmt.Sprintf("### %s - [%s](%s)", pythonTitle(a.Type), title, link))
				}

				switch a.Type {
				case "video":
					if a.VideoID != "" {
						md = append(md, fmt.Sprintf("- [YouTube: %s](https://www.youtube.com/watch?v=%s)", title, a.VideoID))
					} else if href != "" {
						md = append(md, fmt.Sprintf("- [Video Link](%s)", base+href))
					}
					if !opts.TOCOnly && !opts.NoTranscript {
						md = append(md, textutil.ReplaceQuoteMarks(transcriptOrDefault(a.Transcript)))
					}
				case "lab":
					md = append(md, deref(a.Description))
					labName := textutil.ReplaceSpecialChars(title) + ".md"
					box := "x"
					if !a.IsComplete {
						box = " "
					}
					md = append(md, fmt.Sprintf("- [%s] [%s](../labs/%s)", box, title, labName))
				case "quiz":
					if !opts.TOCOnly && len(a.QuizItems) > 0 {
						for i, q := range a.QuizItems {
							stem := strings.ReplaceAll(textutil.CleanText(q.Stem), "\n\n", "")
							md = append(md, fmt.Sprintf("#### Quiz %d.", i+1))
							var ql []string
							ql = append(ql, "> [!important]")
							ql = append(ql, fmt.Sprintf("> **%s**", textutil.CleanText(stem)))
							ql = append(ql, ">")
							for _, opt := range q.Options {
								ql = append(ql, "> - [ ] "+textutil.CleanText(opt.Title))
							}
							md = append(md, strings.Join(ql, "\n"))
						}
					}
				case "link", "html_bundle":
					linkURL := a.Link
					if linkURL == "" && href != "" {
						linkURL = base + href
					}
					md = append(md, fmt.Sprintf("- [%s](%s)", title, linkURL))
					if !opts.TOCOnly && !opts.NoTranscript {
						if a.Transcript != nil && *a.Transcript != "" {
							md = append(md, "\n"+*a.Transcript+"\n")
						}
					}
				case "document":
					if a.LocalDocumentPath != "" {
						filename := a.LocalDocumentPath
						if idx := strings.LastIndex(filename, "/"); idx >= 0 {
							filename = filename[idx+1:]
						}
						md = append(md, fmt.Sprintf("- [%s](../../%s)", filename, a.LocalDocumentPath))
					}
				}
			}
		}
	}

	return strings.Join(md, "\n\n") + "\n"
}

// Path renders a path to Markdown (ports Path.generate_markdown).
func Path(p *model.Path, opts Options) string {
	var md []string
	md = append(md, frontMatter(p.ID.String(), p.Title, "Path", p.PortalKey(), p.URL(), p.DatePublished, nil, p.ScrapedTime))
	md = append(md, fmt.Sprintf("# [%s](%s)", p.Title, p.URL()))

	if !opts.TOCOnly && p.Description != "" {
		md = append(md, p.Description)
	}

	if p.Courses.Len() > 0 {
		md = append(md, "## Courses & Progress")
		var lines []string
		for _, cid := range p.Courses.Keys {
			c := p.Courses.Values[cid]
			name := textutil.ReplaceSpecialChars(c.Name) + ".md"
			lines = append(lines, fmt.Sprintf("* [ ] [%s (%s)](../courses/%s)", c.Name, cid, name))
		}
		md = append(md, strings.Join(lines, "\n"))
	}

	return strings.Join(md, "\n\n") + "\n"
}

// Lab renders a lab to Markdown (ports Lab.generate_markdown).
func Lab(l *model.Lab, opts Options) string {
	var md []string
	md = append(md, frontMatter(l.ID.String(), l.Title, "Lab", l.PortalKey(), l.URL(), nil, nil, l.ScrapedTime))
	md = append(md, fmt.Sprintf("# [%s](%s)", l.Title, l.URL()))

	if !opts.TOCOnly && l.Description != "" {
		md = append(md, l.Description)
	}

	for _, num := range orderedStepKeys(l.Steps.Keys) {
		text := l.Steps.Values[num]
		md = append(md, fmt.Sprintf("## Step %s: %s", num, text))
	}

	return strings.Join(md, "\n\n") + "\n"
}

// orderedStepKeys keeps numeric step keys in numeric order (they are stored as
// "1".."N"); falls back to insertion order for non-numeric keys.
func orderedStepKeys(keys []string) []string {
	allNum := true
	for _, k := range keys {
		if _, err := strconv.Atoi(k); err != nil {
			allNum = false
			break
		}
	}
	if !allNum {
		return keys
	}
	sorted := append([]string(nil), keys...)
	sort.Slice(sorted, func(i, j int) bool {
		a, _ := strconv.Atoi(sorted[i])
		b, _ := strconv.Atoi(sorted[j])
		return a < b
	})
	return sorted
}

func transcriptOrDefault(t *string) string {
	if t == nil {
		return "(No transcript available)"
	}
	return *t
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// pythonTitle mirrors Python's str.title(): upper-case the first letter of each
// run of letters and lower-case the rest. Our activity types are lowercase
// single words (video, quiz, lab, ...), so this is exact for them.
func pythonTitle(s string) string {
	var b strings.Builder
	prevLetter := false
	for _, r := range s {
		isLetter := (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z')
		switch {
		case isLetter && !prevLetter:
			b.WriteRune(upper(r))
		case isLetter:
			b.WriteRune(lower(r))
		default:
			b.WriteRune(r)
		}
		prevLetter = isLetter
	}
	return b.String()
}

func upper(r rune) rune {
	if r >= 'a' && r <= 'z' {
		return r - 32
	}
	return r
}

func lower(r rune) rune {
	if r >= 'A' && r <= 'Z' {
		return r + 32
	}
	return r
}
