package store

import (
	"os"
	"path/filepath"
	"testing"
)

// TestWriteFileAtomic verifies writeFile creates parent dirs, writes the exact
// bytes, overwrites an existing file, and leaves no stray temp files behind (so
// an interrupted run can't accumulate junk next to database.json).
func TestWriteFileAtomic(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nested", "database.json")

	if err := writeFile(path, []byte("first")); err != nil {
		t.Fatalf("writeFile (create): %v", err)
	}
	if b, _ := os.ReadFile(path); string(b) != "first" {
		t.Fatalf("content = %q, want %q", b, "first")
	}
	if err := writeFile(path, []byte("second")); err != nil {
		t.Fatalf("writeFile (overwrite): %v", err)
	}
	if b, _ := os.ReadFile(path); string(b) != "second" {
		t.Fatalf("content after overwrite = %q, want %q", b, "second")
	}

	// The temp file used for the atomic rename must not linger.
	entries, _ := os.ReadDir(filepath.Dir(path))
	for _, e := range entries {
		if e.Name() != "database.json" {
			t.Fatalf("unexpected leftover file: %s", e.Name())
		}
	}
}

// TestLookupName reads a display name back from a database table and returns ""
// for unknown ids.
func TestLookupName(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("CSB_DATA", dir)

	if err := UpsertDoc("public", "paths", map[string]any{"id": "16", "name": "Data Engineer"}); err != nil {
		t.Fatalf("UpsertDoc: %v", err)
	}
	if got := LookupName("public", "paths", "16"); got != "Data Engineer" {
		t.Fatalf("LookupName = %q, want %q", got, "Data Engineer")
	}
	if got := LookupName("public", "paths", "999"); got != "" {
		t.Fatalf("LookupName(unknown) = %q, want empty", got)
	}
}
