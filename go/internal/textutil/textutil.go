// Package textutil ports the small string helpers the Python version uses when
// building filenames and Markdown, so the Go output matches byte-for-byte.
package textutil

import (
	"html"
	"regexp"
	"strings"
)

// ReplaceSpecialChars strips characters that are unsafe in a filename, matching
// Python's util_replace_special_chars (used to derive the .md filename).
func ReplaceSpecialChars(s string) string {
	if s == "" {
		return ""
	}
	r := strings.NewReplacer(
		",", "",
		"/", " ",
		":", "",
		" - ", " ",
	)
	s = r.Replace(s)
	// Note: the " - " -> " " replacement runs before spaces become hyphens,
	// mirroring the ordered chain in the Python original.
	return strings.ReplaceAll(s, " ", "-")
}

// ReplaceQuoteMarks normalises curly quotes to straight ASCII quotes, matching
// Python's util_replace_quote_marks.
func ReplaceQuoteMarks(s string) string {
	if s == "" {
		return ""
	}
	r := strings.NewReplacer(
		"“", "\"", // “ -> "
		"”", "\"", // ” -> "
		"’", "'", // ’ -> '
		"‘", "'", // ‘ -> '
	)
	return r.Replace(s)
}

var tagRe = regexp.MustCompile(`<[^>]*>`)

// StripHTMLTags removes HTML tags from text (approximates Python's HTMLParser
// based stripper closely enough for our transcript/description content).
func StripHTMLTags(s string) string {
	return tagRe.ReplaceAllString(s, "")
}

// CleanText mirrors BaseEntity.clean_text: unescape entities, strip tags,
// normalise newlines, fix quotes, trim.
func CleanText(s string) string {
	if s == "" {
		return ""
	}
	s = StripHTMLTags(html.UnescapeString(s))
	s = strings.ReplaceAll(s, "\r\n", "\n")
	return strings.TrimSpace(ReplaceQuoteMarks(s))
}
