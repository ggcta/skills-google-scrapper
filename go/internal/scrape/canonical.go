package scrape

import (
	"regexp"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// Canonical-URL resolution (partner path fix): partner path pages now list each
// course/lab as a session deep-link with no catalog id, e.g.
// /paths/89/course_sessions/20936064/video/450874 — the trailing 450874 is a
// video id, not the course. The real catalog id lives only on the target page's
// <link rel="canonical"> (…/course_templates/32). These helpers read it so the
// fetch can resolve a deep-link to the real id.

var (
	courseTemplateIDRe = regexp.MustCompile(`/course_templates/(\d+)`)
	catalogLabIDRe     = regexp.MustCompile(`/catalog_lab/(\d+)`)
	focusIDRe          = regexp.MustCompile(`/focuses/(\d+)`)
)

// CanonicalURL returns the page's canonical URL — the <link rel="canonical">
// href, falling back to <meta property="og:url"> — or "" if neither is present.
func CanonicalURL(pageHTML string) string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return ""
	}
	return canonicalURLFromDoc(doc)
}

func canonicalURLFromDoc(doc *goquery.Document) string {
	if href, ok := doc.Find("link[rel='canonical']").First().Attr("href"); ok {
		if h := strings.TrimSpace(href); h != "" {
			return h
		}
	}
	if href, ok := doc.Find("meta[property='og:url']").First().Attr("content"); ok {
		return strings.TrimSpace(href)
	}
	return ""
}

// CourseTemplateIDFromURL extracts the course id from any URL containing
// /course_templates/<id> (e.g. a canonical or final redirect URL).
func CourseTemplateIDFromURL(url string) string {
	if m := courseTemplateIDRe.FindStringSubmatch(url); m != nil {
		return m[1]
	}
	return ""
}

// LabIDFromURL extracts the lab id from a URL containing /catalog_lab/<id> or
// /focuses/<id>.
func LabIDFromURL(url string) string {
	if m := catalogLabIDRe.FindStringSubmatch(url); m != nil {
		return m[1]
	}
	if m := focusIDRe.FindStringSubmatch(url); m != nil {
		return m[1]
	}
	return ""
}

// IsSessionDeepLink reports whether a stored activity URL is a partner session
// deep-link (…/course_sessions/…) that carries no catalog id, so the fetch must
// resolve the real id from the target page's canonical URL rather than trusting
// the trailing segment.
func IsSessionDeepLink(url string) bool {
	return strings.Contains(url, "/course_sessions/") &&
		!courseTemplateIDRe.MatchString(url) &&
		!catalogLabIDRe.MatchString(url) &&
		!focusIDRe.MatchString(url)
}
