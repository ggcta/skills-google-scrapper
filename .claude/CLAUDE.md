# CLAUDE AGENT GUIDES & RULES

## Project Overview

- A Google Skills Scrapper.
- The original code base was built in Python #A.
- The current code base is developed in Go #B for the core and with Tauri for the GUI #C.
- For every change made to either the #A or #B or #C, ensure to cascade the change to the other components.

## Principles

- Keep it simple, stupid (KISS).
- No magic, no hidden side effects.
- Plain and simple.

## Coding

- Always use Linux line endings (LF), NO QUESTION!
- Always use Spaces instead of Tabs for indentation.
- Always Trim Trailing Whitespace (configure your editor accordingly).
- Always use EOF delimiters (the 1 extra empty line or `\n` at the end of the file).
- DO NOT USE MULTIPLE STATEMENTS for a single line.
- Markdown: DO NOT USE MULTIPLE LINES for a single paragraph or block of text.

`.gitattributes`:

```yaml
# Auto detect text files and perform LF normalization
* text=auto eol=lf

```

Sublime Text sample:

```json
{
  "default_line_ending": "unix",
  "translate_tabs_to_spaces": true,
  "draw_white_space": ["selection", "trailing", "isolated"],
	"trim_automatic_white_space": true,
	"show_line_endings": true,
	// Not a must but recommended, utf-8 everywhere
	"show_encoding": true,
}

```

## Components

- core:
  - `app/`, Python: the very first version, supports both CLI and Interactive modes.
  - `go/`, Go: the Go version of the CLI, supports both CLI and Interactive modes.
- gui:
  - `gui/`, Rust/Tauri: the graphical user interface, targets non-development users.

## Commits

- Keep commit messages clean: do NOT add AI attribution or `Co-Authored-By` trailers (e.g. no `Co-Authored-By: Claude ...`).
