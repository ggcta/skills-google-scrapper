// Package scrape parses Google Skills pages into model entities. The HTML
// parsing is separated from the browser so it can be unit-tested offline against
// saved fixtures.
package scrape

import (
	"regexp"
	"strings"

	"github.com/PuerkitoBio/goquery"

	"csb/internal/model"
	"csb/internal/textutil"
)

var siteSuffixRe = regexp.MustCompile(`\s*\|\s*Google.*$`)

// LabContent is the parsed result of a lab page.
type LabContent struct {
	Name        string
	Description string
	Steps       []StepKV // ordered
}

// StepKV is a single ordered step (number -> title).
type StepKV struct {
	Number string
	Title  string
}

// ParseLabHTML extracts a lab's name, description, and ordered steps from its
// page HTML. Ports Lab.parse_steps + the name/description logic in
// Lab.fetch_data. Verifiable offline against saved fixtures.
func ParseLabHTML(html string) (LabContent, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
	if err != nil {
		return LabContent{}, err
	}
	var lc LabContent

	// Name: prefer og:title (strip the "... | Google ..." suffix), else <title>.
	if v, ok := doc.Find("meta[property='og:title']").Attr("content"); ok && v != "" {
		lc.Name = v
	} else if t := strings.TrimSpace(doc.Find("title").First().Text()); t != "" {
		lc.Name = t
	}
	if lc.Name != "" {
		lc.Name = strings.TrimSpace(siteSuffixRe.ReplaceAllString(lc.Name, ""))
	}

	// Description from the meta description tag.
	if v, ok := doc.Find("meta[name='description']").Attr("content"); ok && v != "" {
		lc.Description = textutil.CleanText(v)
	}

	lc.Steps = parseSteps(doc)
	return lc, nil
}

// parseSteps ports Lab.parse_steps: old sidebar outline first, then the
// <h2 id="stepN"> headings inside the rendered instructions.
func parseSteps(doc *goquery.Document) []StepKV {
	var steps []StepKV

	// Old structure: sidebar outline with anchor links.
	outline := doc.Find("ul.lab-content__outline").First()
	if outline.Length() > 0 {
		outline.Find("a").Each(func(_ int, a *goquery.Selection) {
			href, _ := a.Attr("href")
			num := strings.Trim(strings.TrimPrefix(href, "#"), "step")
			steps = append(steps, StepKV{Number: num, Title: a.Text()})
		})
		if len(steps) > 0 {
			return steps
		}
	}

	// New structure: step headings inside the rendered instructions.
	sel := doc.Find(".lab-content__renderable-instructions h2[id^='step']")
	if sel.Length() == 0 {
		sel = doc.Find("h2[id^='step']")
	}
	sel.Each(func(_ int, h *goquery.Selection) {
		id, _ := h.Attr("id")
		num := strings.Replace(id, "step", "", 1)
		if num != "" {
			steps = append(steps, StepKV{Number: num, Title: strings.TrimSpace(h.Text())})
		}
	})
	return steps
}

// ToModel builds a model.Lab from parsed content.
func (lc LabContent) ToModel(id, portalKey string) *model.Lab {
	lab := &model.Lab{
		ID:          model.FlexString(id),
		Title:       lc.Name,
		Description: lc.Description,
		Portal:      portalKey,
	}
	for _, s := range lc.Steps {
		lab.Steps.Set(s.Number, s.Title)
	}
	return lab
}
