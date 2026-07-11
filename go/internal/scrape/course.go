package scrape

import (
	"encoding/json"
	"fmt"
	"html"
	"regexp"
	"strings"

	"github.com/PuerkitoBio/goquery"

	"csb/internal/model"
	"csb/internal/textutil"
)

// multiSpaceRe collapses runs of 2+ whitespace into a paragraph break. It
// includes Unicode separators (\p{Z}, e.g. the non-breaking space   that
// &nbsp; unescapes to) because Python's re `\s` is Unicode-aware while Go's is
// ASCII-only; without \p{Z} a trailing nbsp would survive and diverge.
var multiSpaceRe = regexp.MustCompile(`[\s\p{Z}]{2,}`)

// CourseMeta is the metadata parsed from a course page.
type CourseMeta struct {
	ID            string // @id last segment (public); empty for partner
	Name          string
	Description   string
	DatePublished string
	Topics        []string
	Objectives    []string
	Partner       bool // page had no ld+json
}

// ParseCourseMetadata ports extract_course_metadata (+ the partner fallback).
// Public pages embed an ld+json blob; partner pages fall back to og:title +
// meta description.
func ParseCourseMetadata(pageHTML string) (CourseMeta, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return CourseMeta{}, err
	}
	ld := strings.TrimSpace(doc.Find("script[type='application/ld+json']").First().Text())
	metaDesc, _ := doc.Find("meta[name='description']").Attr("content")

	// Partner: no ld+json.
	if ld == "" {
		return parseCourseMetaPartner(doc, metaDesc)
	}

	var m CourseMeta
	desc := textutil.CleanText(metaDesc)
	desc = strings.TrimSpace(multiSpaceRe.ReplaceAllString(desc, "\n\n"))

	var raw map[string]any
	if err := json.Unmarshal([]byte(ld), &raw); err != nil {
		return CourseMeta{}, fmt.Errorf("parse ld+json: %w", err)
	}
	if idv, ok := raw["@id"].(string); ok {
		parts := strings.Split(idv, "/")
		m.ID = parts[len(parts)-1]
	}
	if nv, ok := raw["name"].(string); ok {
		m.Name = strings.TrimSpace(nv)
	}
	m.Description = desc
	if dp, ok := raw["datePublished"].(string); ok {
		m.DatePublished = dp
	}
	m.Topics = coerceStringList(raw["about"])
	m.Objectives = coerceStringList(raw["teaches"])
	return m, nil
}

func parseCourseMetaPartner(doc *goquery.Document, metaDesc string) (CourseMeta, error) {
	m := CourseMeta{Partner: true, Topics: []string{}, Objectives: []string{}}
	if v, ok := doc.Find("meta[property='og:title']").Attr("content"); ok && v != "" {
		m.Name = strings.TrimSpace(siteSuffixRe.ReplaceAllString(v, ""))
	}
	if m.Name == "" {
		return m, fmt.Errorf("partner course name not found")
	}
	if metaDesc != "" {
		d := textutil.CleanText(metaDesc)
		m.Description = strings.TrimSpace(multiSpaceRe.ReplaceAllString(d, "\n\n"))
	}
	return m, nil
}

// coerceStringList turns schema.org about/teaches (strings or {name} objects)
// into a plain []string.
func coerceStringList(v any) []string {
	out := []string{}
	items, ok := v.([]any)
	if !ok {
		return out
	}
	for _, it := range items {
		switch x := it.(type) {
		case string:
			out = append(out, x)
		case map[string]any:
			if n, ok := x["name"].(string); ok {
				out = append(out, n)
			}
		}
	}
	return out
}

// ParseCourseOutline ports extract_course_outline: the modules JSON lives in the
// "modules" attribute of <ql-contents-menu> (or legacy <ql-course-outline>).
func ParseCourseOutline(pageHTML string) ([]model.Module, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return nil, err
	}
	raw := ""
	if v, ok := doc.Find("ql-contents-menu").First().Attr("modules"); ok {
		raw = v
	} else if v, ok := doc.Find("ql-course-outline").First().Attr("modules"); ok {
		raw = v
	}
	if raw == "" {
		return nil, fmt.Errorf("ql-contents-menu or ql-course-outline not found")
	}
	var modules []model.Module
	if err := json.Unmarshal([]byte(html.UnescapeString(raw)), &modules); err != nil {
		// Some pages don't HTML-escape the attribute; retry raw.
		if err2 := json.Unmarshal([]byte(raw), &modules); err2 != nil {
			return nil, fmt.Errorf("parse modules json: %w", err)
		}
	}
	return modules, nil
}

// ParseVideo ports process_video: extract the YouTube id and joined transcript
// from <ql-youtube-video>. The transcript is always extracted into the data (#12);
// whether it renders into Markdown is decided later at generation time.
func ParseVideo(pageHTML string) (videoID, transcript string) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return "", "(No video transcript.)"
	}
	v := doc.Find("ql-youtube-video").First()
	videoID, _ = v.Attr("videoId")
	if videoID == "" {
		videoID, _ = v.Attr("videoid")
	}
	tData, ok := v.Attr("transcript")
	if !ok || tData == "" {
		return videoID, "(No video transcript.)"
	}
	var segs []struct {
		Text string `json:"text"`
	}
	if err := json.Unmarshal([]byte(tData), &segs); err != nil {
		return videoID, "(No video transcript.)"
	}
	parts := make([]string, len(segs))
	for i, s := range segs {
		parts[i] = s.Text
	}
	return videoID, strings.Join(parts, " ")
}

// ParseQuizItems ports process_quiz's extraction: the quiz payload lives in the
// "quizversion" attribute of <ql-quiz> and contains a quizItems array.
func ParseQuizItems(pageHTML string) ([]model.QuizItem, bool) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return nil, false
	}
	q := doc.Find("ql-quiz").First()
	data, ok := q.Attr("quizversion")
	if !ok || data == "" {
		return nil, false
	}
	var payload struct {
		QuizItems []model.QuizItem `json:"quizItems"`
	}
	if err := json.Unmarshal([]byte(data), &payload); err != nil {
		return nil, false
	}
	return payload.QuizItems, true
}

// ParseActivityLink ports the link extraction shared by process_link and
// process_html_bundle: the document-link anchor href, else the iframe src.
func ParseActivityLink(pageHTML string) string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return ""
	}
	if a := doc.Find("ql-card.document-link a").First(); a.Length() > 0 {
		if href, ok := a.Attr("href"); ok {
			return href
		}
	}
	if f := doc.Find("ql-iframe").First(); f.Length() > 0 {
		if src, ok := f.Attr("src"); ok {
			return src
		}
	}
	return ""
}

// ParseDocumentDownloadHref ports process_document's download-link discovery.
func ParseDocumentDownloadHref(pageHTML string) string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return ""
	}
	for _, sel := range []string{
		`ql-button[icon="download"]`,
		`div.download-document ql-button`,
		`a[aria-label="Download document"]`,
		`a#link`,
	} {
		if el := doc.Find(sel).First(); el.Length() > 0 {
			if href, ok := el.Attr("href"); ok && href != "" {
				return href
			}
		}
	}
	return ""
}

// ParseLabReviewID ports the lab_review_lab_id lookup in process_lab; returns
// "" when the hidden input is absent (caller falls back to the activity id).
func ParseLabReviewID(pageHTML string) string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return ""
	}
	if v, ok := doc.Find("#lab_review_lab_id").First().Attr("value"); ok {
		return strings.TrimSpace(v)
	}
	return ""
}

// ParseLabStepsFromHTML exposes step parsing for the course lab pipeline.
func ParseLabStepsFromHTML(pageHTML string) []StepKV {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(pageHTML))
	if err != nil {
		return nil
	}
	return parseSteps(doc)
}
