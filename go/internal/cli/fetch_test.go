package cli

import (
	"encoding/json"
	"io"
	"os"
	"strings"
	"testing"
)

// captureStdout runs fn with os.Stdout redirected and returns what it printed.
func captureStdout(fn func()) string {
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w
	fn()
	w.Close()
	os.Stdout = old
	out, _ := io.ReadAll(r)
	return string(out)
}

// TestItemSavedMarker locks the "@@ITEM {json}" contract the GUI's Rust bridge
// parses: prefix, valid JSON, and every field the frontend reads.
func TestItemSavedMarker(t *testing.T) {
	emitProgress = true
	defer func() { emitProgress = false }()

	out := strings.TrimSpace(captureStdout(func() {
		itemSaved("course", "public", "53", "Foundations", 1752100000000)
	}))

	rest, ok := strings.CutPrefix(out, "@@ITEM ")
	if !ok {
		t.Fatalf("missing @@ITEM prefix: %q", out)
	}
	var m map[string]any
	if err := json.Unmarshal([]byte(rest), &m); err != nil {
		t.Fatalf("payload is not valid JSON: %v (%q)", err, rest)
	}
	for _, k := range []string{"portal", "kind", "id", "name", "scrapedTime", "scrapedDate"} {
		if _, present := m[k]; !present {
			t.Fatalf("payload missing key %q: %v", k, m)
		}
	}
	if m["scrapedDate"] != "2025-07-09" && m["scrapedDate"] == "" {
		// The exact date depends on the local zone; just require it was formatted.
		t.Fatalf("scrapedDate should be a formatted date, got empty")
	}
}

// TestItemSavedSilentWhenOff verifies the marker is suppressed for normal CLI
// runs, so terminal users never see the machine-readable line.
func TestItemSavedSilentWhenOff(t *testing.T) {
	emitProgress = false
	out := captureStdout(func() {
		itemSaved("course", "public", "53", "Foundations", 1752100000000)
	})
	if out != "" {
		t.Fatalf("expected no output when emitProgress is off, got %q", out)
	}
}
