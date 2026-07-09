package logx

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var tsLine = regexp.MustCompile(`^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} `)

// TestStampPerLine checks each non-empty line gets a millisecond timestamp
// prefix and blank lines (leading/trailing "\n") are preserved as-is.
func TestStampPerLine(t *testing.T) {
	out := stamp("\n--- Path 3644 ---\n")
	lines := strings.Split(out, "\n")
	// "\n--- ... ---\n" -> ["", "<ts> --- ... ---", ""]
	if lines[0] != "" {
		t.Fatalf("leading blank line not preserved: %q", lines[0])
	}
	if !tsLine.MatchString(lines[1]) || !strings.HasSuffix(lines[1], "--- Path 3644 ---") {
		t.Fatalf("content line not timestamped correctly: %q", lines[1])
	}
	if lines[2] != "" {
		t.Fatalf("trailing newline not preserved: %q", lines[2])
	}
}

// TestInitAndFileCopy verifies Init creates a per-run file and that the file
// copy is timestamped with ANSI colour codes stripped.
func TestInitAndFileCopy(t *testing.T) {
	dir := t.TempDir()
	path, err := Init(dir)
	if err != nil {
		t.Fatalf("Init: %v", err)
	}
	defer Close()

	if filepath.Dir(path) != dir {
		t.Fatalf("log file not in %s: %s", dir, path)
	}
	if !strings.HasPrefix(filepath.Base(path), "skills-scraper-") || !strings.HasSuffix(path, ".log") {
		t.Fatalf("unexpected log filename: %s", path)
	}

	Printf("\033[35m--- Processing Path 16 ---\033[0m\n")
	Close() // flush

	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read log: %v", err)
	}
	content := string(b)
	if strings.Contains(content, "\033[") {
		t.Fatalf("ANSI codes not stripped from file copy: %q", content)
	}
	if !tsLine.MatchString(content) || !strings.Contains(content, "--- Processing Path 16 ---") {
		t.Fatalf("file copy missing timestamp/text: %q", content)
	}
}
