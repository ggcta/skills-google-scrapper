package scrape

import (
	"html"
	"regexp"
	"strings"
)

// ExtractLessonContent ports _extract_lesson_content: pull one lesson's items
// out of the external course data (fetched via __fetchCourse) and render them.
func ExtractLessonContent(courseData map[string]any, lessonID string) string {
	lessons := lessonsFrom(courseData)
	var target map[string]any
	for _, l := range lessons {
		lm, ok := l.(map[string]any)
		if !ok {
			continue
		}
		if id, _ := lm["id"].(string); id == lessonID {
			target = lm
			break
		}
	}
	if target == nil {
		return ""
	}
	var parts []string
	if items, ok := target["items"].([]any); ok {
		for _, it := range items {
			if im, ok := it.(map[string]any); ok {
				if p := parseLessonItem(im); p != "" {
					parts = append(parts, p)
				}
			}
		}
	}
	return strings.Join(parts, "\n\n")
}

func lessonsFrom(courseData map[string]any) []any {
	if c, ok := courseData["course"].(map[string]any); ok {
		if l, ok := c["lessons"].([]any); ok {
			return l
		}
	}
	if l, ok := courseData["lessons"].([]any); ok {
		return l
	}
	return nil
}

// parseLessonItem ports _parse_lesson_item: heading/paragraph/list/image, with
// nested items handled recursively.
func parseLessonItem(item map[string]any) string {
	if sub, ok := item["items"].([]any); ok {
		var out []string
		for _, s := range sub {
			if sm, ok := s.(map[string]any); ok {
				if p := parseLessonItem(sm); p != "" {
					out = append(out, p)
				}
			}
		}
		return strings.Join(out, "\n\n")
	}
	if h, ok := item["heading"].(string); ok {
		heading := htmlToMarkdown(h)
		if !strings.HasPrefix(heading, "#") {
			return "#### " + heading
		}
		return heading
	}
	if p, ok := item["paragraph"].(string); ok {
		return htmlToMarkdown(p)
	}
	if l, ok := item["list"].(string); ok {
		return htmlToMarkdown(l)
	}
	if img, ok := item["image"].(map[string]any); ok {
		src, _ := img["src"].(string)
		alt, _ := img["alt"].(string)
		if alt == "" {
			alt = "Image"
		}
		if src != "" {
			return "![" + alt + "](" + src + ")"
		}
	}
	return ""
}

// htmlToMarkdown ports _html_to_markdown: a best-effort regex HTML→Markdown
// converter. The substitution order matches the Python original exactly.
var htmlMDSubs = []struct {
	re   *regexp.Regexp
	with string
}{
	{regexp.MustCompile(`<div[^>]*>`), ""},
	{regexp.MustCompile(`</div>`), "\n"},
	{regexp.MustCompile(`<p[^>]*>`), ""},
	{regexp.MustCompile(`</p>`), "\n\n"},
	{regexp.MustCompile(`<strong[^>]*>`), "**"},
	{regexp.MustCompile(`</strong>`), "**"},
	{regexp.MustCompile(`<b[^>]*>`), "**"},
	{regexp.MustCompile(`</b>`), "**"},
	{regexp.MustCompile(`<em[^>]*>`), "*"},
	{regexp.MustCompile(`</em>`), "*"},
	{regexp.MustCompile(`<i[^>]*>`), "*"},
	{regexp.MustCompile(`</i>`), "*"},
	{regexp.MustCompile(`<ul[^>]*>`), ""},
	{regexp.MustCompile(`</ul>`), ""},
	{regexp.MustCompile(`<ol[^>]*>`), ""},
	{regexp.MustCompile(`</ol>`), ""},
	{regexp.MustCompile(`<li[^>]*>`), "- "},
	{regexp.MustCompile(`</li>`), "\n"},
	{regexp.MustCompile(`<h1[^>]*>`), "# "},
	{regexp.MustCompile(`</h1>`), "\n\n"},
	{regexp.MustCompile(`<h2[^>]*>`), "## "},
	{regexp.MustCompile(`</h2>`), "\n\n"},
	{regexp.MustCompile(`<h3[^>]*>`), "### "},
	{regexp.MustCompile(`</h3>`), "\n\n"},
	{regexp.MustCompile(`<span[^>]*>`), ""},
	{regexp.MustCompile(`</span>`), ""},
}

var collapseNewlinesRe = regexp.MustCompile(`\n\s*\n`)

func htmlToMarkdown(content string) string {
	if content == "" {
		return ""
	}
	for _, s := range htmlMDSubs {
		content = s.re.ReplaceAllString(content, s.with)
	}
	content = html.UnescapeString(content)
	content = collapseNewlinesRe.ReplaceAllString(content, "\n")
	return strings.TrimSpace(content)
}
