package store

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"csb/internal/model"
	"csb/internal/textutil"
)

// TestMarkdownPathForID checks the resolver errors for an unfetched item and,
// once stored, returns an absolute vault path whose filename is the sanitized
// title (the same rule the writer uses), so the GUI opens the right file.
func TestMarkdownPathForID(t *testing.T) {
	data := t.TempDir()
	vault := t.TempDir()
	t.Setenv("CSB_DATA", data)
	t.Setenv("CSB_VAULT", vault)

	if _, err := MarkdownPathForID("public", "courses", "53"); !errors.Is(err, ErrNotStored) {
		t.Fatalf("want ErrNotStored for unfetched item, got %v", err)
	}

	c := &model.Course{ID: model.FlexString("53"), Title: "Data: A/B Course", Portal: "public"}
	if err := SaveCourseEntity(c); err != nil {
		t.Fatalf("SaveCourseEntity: %v", err)
	}
	got, err := MarkdownPathForID("public", "courses", "53")
	if err != nil {
		t.Fatalf("resolve: %v", err)
	}
	if !filepath.IsAbs(got) {
		t.Fatalf("path not absolute: %s", got)
	}
	want := filepath.Join(vault, "public", "courses", textutil.ReplaceSpecialChars("Data: A/B Course")+".md")
	if got != want {
		t.Fatalf("path = %s, want %s", got, want)
	}
}

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
