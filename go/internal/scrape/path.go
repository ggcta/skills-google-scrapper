package scrape

import (
	"encoding/json"
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
		return parsePathLDJSON(ld)
	}
	return parsePathPartner(doc, portalKey), nil
}

func parsePathLDJSON(ld string) (PathContent, error) {
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
	for _, c := range raw.HasPart {
		parts := strings.Split(c.URL, "/")
		id := parts[len(parts)-1]
		pc.Courses = append(pc.Courses, model.CourseRef{
			ID:   id,
			Type: c.Type,
			Name: strings.TrimSpace(c.Name),
			URL:  strings.TrimSpace(c.URL),
		})
	}
	return pc, nil
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
