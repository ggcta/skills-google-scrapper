package scrape

import (
	"os"
	"path/filepath"
	"testing"
)

// TestParseLabFixture checks the lab parser against the saved partner focus page
// (data/sample_html/104653.html), which has 13 step headings.
func TestParseLabFixture(t *testing.T) {
	path := filepath.Join("..", "..", "..", "data", "sample_html", "104653.html")
	b, err := os.ReadFile(path)
	if err != nil {
		t.Skipf("fixture not available: %v", err)
	}
	lc, err := ParseLabHTML(string(b))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if lc.Name == "" {
		t.Errorf("expected a lab name, got empty")
	}
	if len(lc.Steps) != 13 {
		t.Errorf("expected 13 steps, got %d: %+v", len(lc.Steps), lc.Steps)
	}
	t.Logf("name=%q description=%.60q steps=%d", lc.Name, lc.Description, len(lc.Steps))
	for _, s := range lc.Steps {
		t.Logf("  step %s: %s", s.Number, s.Title)
	}
}
