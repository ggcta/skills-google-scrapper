package scrape

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func readLocalFixture(t *testing.T, name string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Skipf("fixture %s not available: %v", name, err)
	}
	return string(b)
}

// TestCanonicalCourseID verifies the partner-path fix's resolution key: a course
// page identifies its real course_templates id via its canonical URL, and the
// partner metadata id is read from it (there is no ld+json @id on partner pages).
func TestCanonicalCourseID(t *testing.T) {
	h := readLocalFixture(t, "partner_course_32.html")

	canon := CanonicalURL(h)
	if !strings.Contains(canon, "/course_templates/32") {
		t.Fatalf("canonical = %q, want it to contain /course_templates/32", canon)
	}
	if got := CourseTemplateIDFromURL(canon); got != "32" {
		t.Errorf("CourseTemplateIDFromURL(%q) = %q, want 32", canon, got)
	}
	m, err := ParseCourseMetadata(h)
	if err != nil {
		t.Fatalf("metadata: %v", err)
	}
	if !m.Partner {
		t.Errorf("expected partner page (no ld+json)")
	}
	if m.ID != "32" {
		t.Errorf("partner course id from canonical = %q, want 32", m.ID)
	}
}

// TestPartnerPathSessionDeepLinks documents the bug this fix targets: a partner
// path's course activities are session deep-links with NO catalog id, so their
// stored URL trips IsSessionDeepLink (the signal to resolve the real id at fetch
// time) and the trailing-segment id is a video/quiz id — not the course.
func TestPartnerPathSessionDeepLinks(t *testing.T) {
	h := readLocalFixture(t, "partner_path_89.html")

	pc, err := ParsePathHTML(h, "partner")
	if err != nil {
		t.Fatalf("ParsePathHTML: %v", err)
	}
	if len(pc.Courses) != 3 {
		t.Fatalf("got %d courses, want 3", len(pc.Courses))
	}
	wantTitles := []string{
		"Architecting with Google Kubernetes Engine: Foundations",
		"Architecting with Google Kubernetes Engine: Workloads",
		"Architecting with Google Kubernetes Engine: Production",
	}
	for i, c := range pc.Courses {
		if c.Name != wantTitles[i] {
			t.Errorf("course[%d].Name = %q, want %q", i, c.Name, wantTitles[i])
		}
		if !strings.Contains(c.URL, "/course_sessions/") {
			t.Errorf("course[%d].URL = %q, want a session deep-link", i, c.URL)
		}
		if !IsSessionDeepLink(c.URL) {
			t.Errorf("course[%d]: IsSessionDeepLink(%q) = false, want true", i, c.URL)
		}
		// The trailing-segment id is a video/quiz id, not the real course id.
		if CourseTemplateIDFromURL(c.URL) != "" {
			t.Errorf("course[%d].URL unexpectedly contains a course_templates id: %q", i, c.URL)
		}
	}
}
