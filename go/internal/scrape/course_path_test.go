package scrape

import (
	"os"
	"path/filepath"
	"testing"
)

func readFixture(t *testing.T, name string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("..", "..", "..", "data", "sample_html", name))
	if err != nil {
		t.Skipf("fixture %s not available: %v", name, err)
	}
	return string(b)
}

// TestParsePartnerCourse checks metadata + outline against 35.html (partner
// course, no ld+json, 6 modules per the fixtures).
func TestParsePartnerCourse(t *testing.T) {
	h := readFixture(t, "35.html")
	m, err := ParseCourseMetadata(h)
	if err != nil {
		t.Fatalf("metadata: %v", err)
	}
	if !m.Partner {
		t.Errorf("expected partner (no ld+json), got public")
	}
	if m.Name == "" {
		t.Errorf("expected a course name")
	}
	mods, err := ParseCourseOutline(h)
	if err != nil {
		t.Fatalf("outline: %v", err)
	}
	if len(mods) != 6 {
		t.Errorf("expected 6 modules, got %d", len(mods))
	}
	t.Logf("name=%q modules=%d desc=%.50q", m.Name, len(mods), m.Description)
}

// TestParsePartnerPath checks the partner path parser against 4343.html
// (7 activity cards per the fixtures).
func TestParsePartnerPath(t *testing.T) {
	h := readFixture(t, "4343.html")
	pc, err := ParsePathHTML(h, "partner")
	if err != nil {
		t.Fatalf("path: %v", err)
	}
	if pc.Name == "" {
		t.Errorf("expected a path name")
	}
	if len(pc.Courses) != 7 {
		t.Errorf("expected 7 activities, got %d", len(pc.Courses))
	}
	t.Logf("name=%q activities=%d", pc.Name, len(pc.Courses))
	for _, c := range pc.Courses {
		t.Logf("  [%s] %s (%s)", c.Type, c.Name, c.ID)
	}
}
