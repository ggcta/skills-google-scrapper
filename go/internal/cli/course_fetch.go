package cli

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"csb/internal/browser"
	"csb/internal/logx"
	"csb/internal/mdgen"
	"csb/internal/model"
	"csb/internal/portal"
	"csb/internal/scrape"
	"csb/internal/store"
	"csb/internal/textutil"
)

const activitySettle = 1200 * time.Millisecond

var sessionHrefRe = regexp.MustCompile(`/course_sessions/[^/]+`)

// fetchCourse ports Course.extract_transcript end to end.
func fetchCourse(sess *browser.Session, portalKey, id string, force, noMD, tocOnly, noTranscript bool) error {
	// Skip before any navigation when the course is already fully scraped
	// (backlog #6/#7); --force re-fetches (#8). This is a local check (no browser),
	// distinct from the online datePublished freshness check further below.
	if !force && courseComplete(portalKey, id) {
		logx.Printf("•-• [+] Course %s already complete.\n", labelFor(portalKey, "courses", id))
		return nil
	}
	courseURL := portal.Get(portalKey).Courses + "/" + id
	logx.Printf("(fetch_course_page) Fetching: %s\n", courseURL)
	html, finalURL, err := sess.Navigate(courseURL, activitySettle)
	if err != nil {
		return err
	}
	html, err = ensureAuthenticated(sess, courseURL, html, finalURL, activitySettle, "course "+id)
	if err != nil {
		return err
	}

	// Stored publish date, for the skip check.
	storedDate := ""
	if existing, _ := store.LoadCourse(portalKey, id); existing != nil && existing.DatePublished != nil {
		storedDate = *existing.DatePublished
	}

	meta, err := scrape.ParseCourseMetadata(html)
	if err != nil {
		return fmt.Errorf("metadata: %w", err)
	}
	// Skip (public only) when the publish date is unchanged and not forced.
	if !force && !meta.Partner && meta.DatePublished != "" && meta.DatePublished == storedDate {
		logx.Printf("(extract_course_metadata) Course %s already extracted. datePublished: %s\n", id, meta.DatePublished)
		return nil
	}

	effectiveID := id
	if meta.ID != "" {
		effectiveID = meta.ID
	}

	modules, err := scrape.ParseCourseOutline(html)
	if err != nil {
		return fmt.Errorf("outline: %w", err)
	}

	dp := meta.DatePublished
	topics := meta.Topics
	course := &model.Course{
		ID:            model.FlexString(effectiveID),
		Title:         meta.Name,
		Description:   meta.Description,
		Portal:        portalKey,
		DatePublished: &dp,
		Objectives:    meta.Objectives,
		Topics:        &topics,
		Modules:       modules,
	}

	if !tocOnly {
		base := portal.Get(portalKey).Base
		for mi := range course.Modules {
			m := &course.Modules[mi]
			logx.Printf("(module) %s\n", strings.TrimSpace(m.Title))
			m.Description = textutil.CleanText(m.Description)
			for si := range m.Steps {
				for ai := range m.Steps[si].Activities {
					processActivity(sess, base, effectiveID, portalKey, &m.Steps[si].Activities[ai], noTranscript, force)
				}
			}
		}
	}

	if sess.Interrupted() {
		return errInterrupted
	}
	if err := store.SaveCourseEntity(course); err != nil {
		return err
	}
	// Keep the courses collection name in sync.
	_ = store.UpsertCollectionName(portalKey, "courses", effectiveID, course.Title)
	if !noMD {
		if _, err := store.WriteCourseMarkdown(course, mdgen.Course(course, mdgen.Options{TOCOnly: tocOnly, NoTranscript: noTranscript})); err != nil {
			return err
		}
	}
	itemSaved("course", portalKey, effectiveID, course.Title, course.ScrapedTime)
	logx.Printf("•-• COMPLETED: %s - %s\n", effectiveID, course.Title)
	return nil
}

// processActivity ports process_step's per-type dispatch, enriching the activity
// in place with transcripts, links, quiz items, video ids, or documents.
func processActivity(sess *browser.Session, base, courseID, portalKey string, a *model.Activity, noTranscript, force bool) {
	// Fix session hrefs back to the template.
	if a.Href != "" && strings.Contains(a.Href, "/course_sessions/") {
		a.Href = sessionHrefRe.ReplaceAllString(a.Href, "/course_templates/"+courseID)
	}
	fullURL := base + a.Href

	switch a.Type {
	case "video":
		html, _, err := sess.Navigate(fullURL, activitySettle)
		if err != nil {
			logx.Printf("(process_video) Error: %v\n", err)
			return
		}
		vid, transcript := scrape.ParseVideo(html, noTranscript)
		if vid != "" {
			a.VideoID = vid
		}
		a.Transcript = strPtr(transcript)

	case "lab":
		processCourseLab(sess, base, courseID, portalKey, a, force)

	case "quiz":
		if _, _, err := sess.Navigate(fullURL, activitySettle); err != nil {
			logx.Printf("(process_quiz) Error: %v\n", err)
			return
		}
		sess.ClickStartQuiz()
		html, err := sess.PageHTML()
		if err != nil {
			return
		}
		if items, ok := scrape.ParseQuizItems(html); ok {
			a.QuizItems = items
		}

	case "link":
		html, _, err := sess.Navigate(fullURL, activitySettle)
		if err != nil {
			logx.Printf("(process_link) Error: %v\n", err)
			return
		}
		a.Link = scrape.ParseActivityLink(html)
		maybeExternalTranscript(sess, a, false) // link always tries (Python does)

	case "html_bundle":
		html, _, err := sess.Navigate(fullURL, activitySettle)
		if err != nil {
			logx.Printf("(process_html_bundle) Error: %v\n", err)
			return
		}
		a.Link = scrape.ParseActivityLink(html)
		maybeExternalTranscript(sess, a, noTranscript)

	case "document":
		downloadDocument(sess, base, courseID, portalKey, a)
	}
}

// maybeExternalTranscript fetches Rise/Storage lesson content for storage.google
// links, matching process_link / process_html_bundle.
func maybeExternalTranscript(sess *browser.Session, a *model.Activity, noTranscript bool) {
	if noTranscript {
		return
	}
	if a.Link == "" || !strings.Contains(a.Link, "storage.googleapis.com") || !strings.Contains(a.Link, "#/lessons/") {
		return
	}
	lessonID := a.Link[strings.LastIndex(a.Link, "#/lessons/")+len("#/lessons/"):]
	if _, _, err := sess.Navigate(strings.Split(a.Link, "#")[0], 3*time.Second); err != nil {
		return
	}
	var data map[string]any
	expr := `(async () => { if (typeof __fetchCourse === 'function') { return await __fetchCourse(); } return null; })()`
	if err := sess.EvalAsync(expr, &data); err != nil || data == nil {
		return
	}
	if transcript := scrape.ExtractLessonContent(data, lessonID); transcript != "" {
		a.Transcript = strPtr(transcript)
		logx.Printf("  •-• [+] external transcript (%d chars)\n", len(transcript))
	}
}

// processCourseLab ports process_lab: fetch the lab via the template URL and
// persist it as its own entity.
func processCourseLab(sess *browser.Session, base, courseID, portalKey string, a *model.Activity, force bool) {
	templateURL := fmt.Sprintf("%s/course_templates/%s/labs/%s", base, courseID, a.ID.String())
	html, finalURL, err := sess.Navigate(templateURL, activitySettle)
	if err != nil || strings.Contains(finalURL, "sign_in") {
		logx.Printf("(process_lab) skipped %s (nav/auth)\n", a.ID.String())
		return
	}
	labID := scrape.ParseLabReviewID(html)
	if labID == "" {
		labID = a.ID.String()
	}
	if !force {
		if existing, _ := store.LoadLab(portalKey, labID); existing != nil && existing.Title != "" {
			logx.Printf("(process_lab) •-• [+] Existed: %s - %s\n", labID, existing.Title)
			return
		}
	}
	steps := scrape.ParseLabStepsFromHTML(html)
	lab := &model.Lab{
		ID:          model.FlexString(labID),
		Title:       strings.TrimSpace(a.Title),
		Description: textutil.CleanText(derefStrPtr(a.Description)),
		Portal:      portalKey,
	}
	for _, s := range steps {
		lab.Steps.Set(s.Number, s.Title)
	}
	if err := store.SaveLabEntity(lab); err != nil {
		logx.Printf("(process_lab) save error: %v\n", err)
		return
	}
	_, _ = store.WriteLabMarkdown(lab, mdgen.Lab(lab, mdgen.Options{}))
	itemSaved("lab", portalKey, labID, lab.Title, lab.ScrapedTime)
	logx.Printf("(process_lab) •-• [+] %s - %s (%d steps)\n", labID, lab.Title, lab.Steps.Len())
}

// downloadDocument ports process_document: find the download link, resolve the
// filename, and save the file (with browser cookies) under the shared materials
// folder.
func downloadDocument(sess *browser.Session, base, courseID, portalKey string, a *model.Activity) {
	fullURL := base + a.Href
	html, finalURL, err := sess.Navigate(fullURL, activitySettle)
	if err != nil || strings.Contains(finalURL, "sign_in") {
		return
	}
	href := scrape.ParseDocumentDownloadHref(html)
	if href == "" {
		logx.Println("(process_document) [!] Download link not found.")
		return
	}
	if !strings.HasPrefix(href, "http") && strings.HasPrefix(href, "/") {
		href = strings.TrimRight(base, "/") + href
	}

	filename := documentFilename(href)
	rel := fmt.Sprintf("materials/courses/%s/%s", courseID, filename)
	a.LocalDocumentPath = rel
	dst := filepath.Join(store.VaultRoot(), "materials", "courses", courseID, filename)

	if _, err := os.Stat(dst); err == nil {
		logx.Printf("(process_document) •-• [+] Existed: %s\n", filename)
		return
	}
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		logx.Printf("(process_document) mkdir error: %v\n", err)
		return
	}

	req, _ := http.NewRequest("GET", href, nil)
	if cookies, err := sess.Cookies(); err == nil {
		var pairs []string
		for _, c := range cookies {
			pairs = append(pairs, c.Name+"="+c.Value)
		}
		if len(pairs) > 0 {
			req.Header.Set("Cookie", strings.Join(pairs, "; "))
		}
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		logx.Printf("(process_document) download error: %v\n", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		logx.Printf("(process_document) download HTTP %d\n", resp.StatusCode)
		return
	}
	f, err := os.Create(dst)
	if err != nil {
		return
	}
	defer f.Close()
	if _, err := io.Copy(f, resp.Body); err != nil {
		logx.Printf("(process_document) write error: %v\n", err)
		return
	}
	logx.Printf("(process_document) •-• [+] Saved: %s\n", filename)
}

var cdFilenameRe = regexp.MustCompile(`filename="?([^";]+)"?`)

// documentFilename ports the filename resolution: prefer the
// response-content-disposition query param, else the URL path basename.
func documentFilename(fileURL string) string {
	u, err := url.Parse(fileURL)
	if err != nil {
		return "download"
	}
	if rcd := u.Query().Get("response-content-disposition"); rcd != "" {
		if m := cdFilenameRe.FindStringSubmatch(rcd); m != nil {
			if name, err := url.QueryUnescape(m[1]); err == nil {
				return name
			}
			return m[1]
		}
	}
	name := filepath.Base(u.Path)
	if dec, err := url.QueryUnescape(name); err == nil {
		return dec
	}
	return name
}

func strPtr(s string) *string { return &s }

func derefStrPtr(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
