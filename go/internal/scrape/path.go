package scrape

import (
	"encoding/json"
	"html"
	"regexp"
	"strings"

	"github.com/PuerkitoBio/goquery"

	"csb/internal/model"
	"csb/internal/portal"
	"csb/internal/textutil"
)

// partnerIDMarkers are the URL segments whose following number is the canonical
// catalog id (a started item deep-links to a session id otherwise).
var partnerIDMarkers = []string{"course_templates", "catalog_lab", "focuses", "labs"}

// PathContent is a parsed path page.
type PathContent struct {
	Name          string
	Description   string
	DatePublished string
	Courses       []model.CourseRef // ordered
}

// ParsePathHTML ports Path.fetch_data: prefer the public ld+json blob, else the
// partner DOM (<h1 class="learning-plan-title"> + <ql-activity-card>).
func ParsePathHTML(pageHTML, portalKey string) (PathContent, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return PathContent{}, err
	}
	ld := strings.TrimSpace(doc.Find("script[type='application/ld+json']").First().Text())
	if ld != "" {
		return parsePathPublic(doc, ld, portalKey)
	}
	return parsePathPartner(doc, portalKey), nil
}

// focusHrefRe matches a top-level standalone-lab href, e.g.
// "/focuses/2794?parent=catalog&path=20" -> id 2794.
var focusHrefRe = regexp.MustCompile(`^/focuses/(\d+)`)

// courseTemplateHrefRe extracts a course id from a href that contains
// /course_templates/<id> (present for non-started courses).
var courseTemplateHrefRe = regexp.MustCompile(`/course_templates/(\d+)`)

// ldEntry is a hasPart record from the path's ld+json.
type ldEntry struct {
	ID   string // course_templates id from the ld url
	Name string
}

// parsePathPublic consolidates a public path's activity list from two sources.
//
// The ld+json hasPart is unreliable: it labels every entry `@type: "Course"` and
// points a standalone lab's url at a coincidental, unrelated (often paywalled)
// course_templates id — e.g. the lab "A Tour of Google Cloud Hands-on Labs"
// appears as course_templates/1281, which is a different, purchase-gated course
// that isn't in the path at all. So the ld+json urls can't be trusted.
//
// The path's ql-contents-menu is authoritative: each activity's href tells the
// truth — a top-level /focuses/<id> is a genuine standalone lab; anything under
// /paths/<pid>/... is a course (its href only pointing at the user's resume
// spot). We therefore iterate the ql-menu as the source of truth (order + type
// + lab/course ids where present) and consult the ld+json only to supply the
// course id for the session-deep-link case and to enrich names. A lab's bogus
// ld url is never used.
func parsePathPublic(doc *goquery.Document, ld, portalKey string) (PathContent, error) {
	var raw struct {
		Name          string `json:"name"`
		Description   string `json:"description"`
		DatePublished string `json:"datePublished"`
		HasPart       []struct {
			Name string `json:"name"`
			URL  string `json:"url"`
		} `json:"hasPart"`
	}
	if err := json.Unmarshal([]byte(ld), &raw); err != nil {
		return PathContent{}, err
	}
	pc := PathContent{
		Name:          strings.TrimSpace(raw.Name),
		Description:   textutil.CleanText(raw.Description),
		DatePublished: strings.TrimSpace(raw.DatePublished),
	}
	base := portal.Get(portalKey).Base

	// ld+json enrichment: course id + clean name, keyed by normalized title.
	ldByName := make(map[string]ldEntry, len(raw.HasPart))
	for _, c := range raw.HasPart {
		name := strings.TrimSpace(c.Name)
		parts := strings.Split(strings.TrimSpace(c.URL), "/")
		ldByName[normalizeName(name)] = ldEntry{ID: parts[len(parts)-1], Name: name}
	}

	menu := pathMenuActivities(doc)
	if len(menu) == 0 {
		// No contents menu (unusual): fall back to the ld+json as-is. Labs can't
		// be distinguished here, but at least real courses resolve.
		for _, c := range raw.HasPart {
			name := strings.TrimSpace(c.Name)
			parts := strings.Split(strings.TrimSpace(c.URL), "/")
			pc.Courses = append(pc.Courses, model.CourseRef{
				ID: parts[len(parts)-1], Type: "Course", Name: name, URL: strings.TrimSpace(c.URL),
			})
		}
		return pc, nil
	}

	// The ql-contents-menu is authoritative for what's in the path.
	for _, a := range menu {
		title := strings.TrimSpace(a.Title)
		ldHit, hasLD := ldByName[normalizeName(title)]
		name := title
		if hasLD && ldHit.Name != "" {
			name = ldHit.Name
		}

		if m := focusHrefRe.FindStringSubmatch(a.Href); m != nil {
			// Standalone lab: focus id + full focus URL (keep ?parent=…&path=…).
			pc.Courses = append(pc.Courses, model.CourseRef{
				ID: m[1], Type: "lab", Name: name, URL: base + a.Href,
			})
			continue
		}

		// Course: prefer the id in the href; otherwise (a course_sessions
		// resume deep-link) take it from the aligned ld+json entry.
		id := ""
		if m := courseTemplateHrefRe.FindStringSubmatch(a.Href); m != nil {
			id = m[1]
		} else if hasLD {
			id = ldHit.ID
		}
		if id == "" {
			continue // unresolvable — skip rather than fetch the wrong thing
		}
		pc.Courses = append(pc.Courses, model.CourseRef{
			ID: id, Type: "Course", Name: name, URL: base + "/course_templates/" + id,
		})
	}
	return pc, nil
}

// menuActivity is one entry from the path's ql-contents-menu.
type menuActivity struct {
	Href  string `json:"href"`
	Title string `json:"title"`
}

// pathMenuActivities returns the path's ql-contents-menu activities in order.
func pathMenuActivities(doc *goquery.Document) []menuActivity {
	raw, ok := doc.Find("ql-contents-menu").First().Attr("modules")
	if !ok || raw == "" {
		return nil
	}
	var modules []struct {
		Steps []struct {
			Activities []menuActivity `json:"activities"`
		} `json:"steps"`
	}
	if err := json.Unmarshal([]byte(raw), &modules); err != nil {
		if err2 := json.Unmarshal([]byte(html.UnescapeString(raw)), &modules); err2 != nil {
			return nil
		}
	}
	var out []menuActivity
	for _, m := range modules {
		for _, s := range m.Steps {
			out = append(out, s.Activities...)
		}
	}
	return out
}

func normalizeName(s string) string {
	return strings.ToLower(strings.TrimSpace(s))
}

func parsePathPartner(doc *goquery.Document, portalKey string) PathContent {
	var pc PathContent
	pc.Name = strings.TrimSpace(doc.Find("h1.learning-plan-title").First().Text())
	base := portal.Get(portalKey).Base

	doc.Find("ql-activity-card").Each(func(_ int, card *goquery.Selection) {
		rawPath, _ := card.Attr("path")
		rawPath = strings.TrimSpace(rawPath)
		if rawPath == "" {
			return
		}
		cleanHref := strings.TrimRight(strings.Split(rawPath, "?")[0], "/")
		aType, _ := card.Attr("type")
		aType = strings.TrimSpace(aType)
		if aType == "" {
			aType = "course"
		}
		id := extractPartnerActivityID(cleanHref, aType)
		if id == "" {
			return
		}
		name, _ := card.Attr("name")
		pc.Courses = append(pc.Courses, model.CourseRef{
			ID:   id,
			Type: aType,
			Name: strings.TrimSpace(name),
			// Preserve the full href (incl. ?parent=…&path=…) for partner labs.
			URL: base + rawPath,
		})
	})
	return pc
}

// extractPartnerActivityID ports _extract_partner_activity_id.
func extractPartnerActivityID(href, activityType string) string {
	for _, marker := range partnerIDMarkers {
		re := regexp.MustCompile(`/` + regexp.QuoteMeta(marker) + `/(\d+)`)
		if m := re.FindStringSubmatch(href); m != nil {
			return m[1]
		}
	}
	parts := strings.Split(href, "/")
	return parts[len(parts)-1]
}

// ToModel builds a model.Path from parsed content.
func (pc PathContent) ToModel(id, portalKey string) *model.Path {
	dp := pc.DatePublished
	p := &model.Path{
		ID:            model.FlexString(id),
		Title:         pc.Name,
		Description:   pc.Description,
		Portal:        portalKey,
		DatePublished: &dp,
	}
	for _, c := range pc.Courses {
		p.Courses.Set(c.ID, c)
	}
	return p
}
