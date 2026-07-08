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

// parsePathPublic builds the activity list for a public path.
//
// The ld+json hasPart mislabels standalone labs as `Course` entries with a
// bogus course_templates URL (e.g. the lab "A Tour of Google Cloud Hands-on
// Labs" appears as course_templates/1281, a completely different course). The
// path page's ql-contents-menu carries the real per-activity href, where a
// genuine standalone lab is a top-level `/focuses/<id>` (anything under
// `/paths/<id>/...` is a course, its href merely pointing at the user's resume
// position). We take names/course-ids from the ld+json and cross-reference the
// ql-menu by name to correct the lab entries.
func parsePathPublic(doc *goquery.Document, ld, portalKey string) (PathContent, error) {
	var raw struct {
		Name          string `json:"name"`
		Description   string `json:"description"`
		DatePublished string `json:"datePublished"`
		HasPart       []struct {
			Type string `json:"@type"`
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

	hrefByName := pathActivityHrefs(doc)
	base := portal.Get(portalKey).Base

	for _, c := range raw.HasPart {
		name := strings.TrimSpace(c.Name)
		href := hrefByName[normalizeName(name)]
		if m := focusHrefRe.FindStringSubmatch(href); m != nil {
			// Genuine standalone lab: use the focus id and full focus URL
			// (keeping the ?parent=…&path=… query the lab page needs).
			pc.Courses = append(pc.Courses, model.CourseRef{
				ID:   m[1],
				Type: "lab",
				Name: name,
				URL:  base + href,
			})
			continue
		}
		// Course: the ld+json course_templates URL is the correct one.
		parts := strings.Split(c.URL, "/")
		pc.Courses = append(pc.Courses, model.CourseRef{
			ID:   parts[len(parts)-1],
			Type: c.Type,
			Name: name,
			URL:  strings.TrimSpace(c.URL),
		})
	}
	return pc, nil
}

// pathActivityHrefs maps each path activity's (normalized) title to its
// ql-contents-menu href.
func pathActivityHrefs(doc *goquery.Document) map[string]string {
	out := map[string]string{}
	raw, ok := doc.Find("ql-contents-menu").First().Attr("modules")
	if !ok || raw == "" {
		return out
	}
	var modules []struct {
		Steps []struct {
			Activities []struct {
				Href  string `json:"href"`
				Title string `json:"title"`
			} `json:"activities"`
		} `json:"steps"`
	}
	if err := json.Unmarshal([]byte(raw), &modules); err != nil {
		if err2 := json.Unmarshal([]byte(html.UnescapeString(raw)), &modules); err2 != nil {
			return out
		}
	}
	for _, m := range modules {
		for _, s := range m.Steps {
			for _, a := range s.Activities {
				if key := normalizeName(a.Title); key != "" {
					if _, exists := out[key]; !exists {
						out[key] = a.Href
					}
				}
			}
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
