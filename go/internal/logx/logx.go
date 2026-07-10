// Package logx is a small activity logger for the fetch flow. It timestamps
// every line it prints (millisecond precision) and tees the same output to a
// per-run log file, so a run leaves an auditable history on disk.
//
// The console keeps colour; the file copy is plain (ANSI stripped). Output is
// serialized with a mutex so interleaved writers stay line-clean.
package logx

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"csb/internal/config"
)

// TimeLayout is the per-line timestamp: ISO-8601-ish, sortable, millisecond
// precision (e.g. "2026-07-10 14:23:45.123").
const TimeLayout = "2006-01-02 15:04:05.000"

// fileTimeLayout stamps the per-run log filename. Colons are illegal in file
// names on some filesystems, so it uses dashes; millisecond precision is kept.
const fileTimeLayout = "20060102-150405.000"

var (
	mu      sync.Mutex
	logFile *os.File
	ansiRe  = regexp.MustCompile(`\x1b\[[0-9;]*m`)
)

// Dir resolves the log directory: CSB_LOG_DIR env > config paths.logs > "logs"
// (relative to the working directory, matching how the data/vault roots resolve).
func Dir() string {
	return config.Resolve("CSB_LOG_DIR", config.Get().Paths.Logs, "logs")
}

// Init opens a fresh per-run log file under dir (Dir() when dir is empty) and
// returns its path. Logging degrades gracefully: if the file can't be opened,
// output still goes to the console and the error is returned.
func Init(dir string) (string, error) {
	if dir == "" {
		dir = Dir()
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	name := "skills-scraper-" + time.Now().Format(fileTimeLayout) + ".log"
	path := filepath.Join(dir, name)
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return "", err
	}
	mu.Lock()
	logFile = f
	mu.Unlock()
	return path, nil
}

// Close flushes and closes the log file (safe to call when logging never
// started).
func Close() {
	mu.Lock()
	defer mu.Unlock()
	if logFile != nil {
		logFile.Close()
		logFile = nil
	}
}

// stamp prefixes the current timestamp to every non-empty line of msg, leaving
// blank lines blank and preserving newlines (so leading/trailing "\n" spacing
// and "\r" progress updates are kept).
func stamp(msg string) string {
	if msg == "" {
		return ""
	}
	ts := time.Now().Format(TimeLayout)
	var b strings.Builder
	atLineStart := true
	for _, r := range msg {
		if atLineStart && r != '\n' {
			b.WriteString(ts)
			b.WriteByte(' ')
			atLineStart = false
		}
		b.WriteRune(r)
		if r == '\n' {
			atLineStart = true
		}
	}
	return b.String()
}

// emit writes stamped text to the console writer and (ANSI-stripped) to the log
// file.
func emit(console *os.File, msg string) {
	text := stamp(msg)
	mu.Lock()
	defer mu.Unlock()
	fmt.Fprint(console, text)
	if logFile != nil {
		fmt.Fprint(logFile, ansiRe.ReplaceAllString(text, ""))
	}
}

// Printf logs a timestamped line to stdout and the file.
func Printf(format string, a ...any) { emit(os.Stdout, fmt.Sprintf(format, a...)) }

// Println logs a timestamped line (with trailing newline) to stdout and the file.
func Println(a ...any) { emit(os.Stdout, fmt.Sprintln(a...)) }

// Errf logs a timestamped line to stderr and the file.
func Errf(format string, a ...any) { emit(os.Stderr, fmt.Sprintf(format, a...)) }

// Raw writes s to stdout verbatim (no timestamp) and does not touch the log
// file. Used for machine-readable markers like the GUI's "@@ITEM" lines, which
// a wrapping parser reads and which the human log lines already summarize.
func Raw(s string) {
	mu.Lock()
	defer mu.Unlock()
	fmt.Fprint(os.Stdout, s)
}
