# csb — Go rewrite (single binary)

A Go reimplementation of the Cloud Skills Boost scraper. It reads and writes the
**exact same** `data/` and `csbmdvault/` layout as the Python version, so the two
are interchangeable and can be run side by side during the migration. They also
**share the login profile** (`.webdriver_profiles/`), so signing in once works for
both.

Run everything from the repository root (so it finds `data/` and `csbmdvault/`).

## Build

```bash
cd go
go build -o csb .
# then run ../csb from the repo root, or `go run .` from go/
```

Requires Go 1.26+ and Google Chrome (chromedp drives your installed Chrome).

## Status

| Command | State | Notes |
|---|---|---|
| `md` | ✅ Done | Byte-identical to Python across all 194 stored entities. |
| `list` | ✅ Done | Reads the local DB. `--reload` (browser refresh) is pending. |
| `search` | ✅ Done | Whole-doc and `--field` matching; output matches Python. |
| `login` | ✅ Done | Opens a browser to sign in; session shared with Python. |
| `fetch -l` (labs) | ✅ Done | End-to-end; output byte-identical to Python (verified live). |
| `fetch -c` (courses) | ✅ Done | Full pipeline (metadata, outline, transcripts, external Rise/Storage lessons, quizzes, labs, documents). Course 53 verified **byte-identical** live. |
| `fetch -p` (paths) | ✅ Done | Parses the plan and cascades to courses → labs, inheriting flags/portal. |
| `list --reload` | ✅ Done | Refreshes the catalog from the site JSON API (verified: 800 partner courses). |
| `interactive` | ✅ Done | Guided menu with persistent working portal. |

**The Go CLI is now at full functional parity with the Python version.**

Known simplifications in the Go build (do not affect Markdown output):
- The course/lab JSON keeps the Markdown-relevant fields and drops unused
  catalog flags (`isLocked`, `duration`, `inProgress`, `score`, `disabled`,
  `paid`); `quizItems` keep `stem`/`options`. Both tools still generate
  identical Markdown.
- The database (`database.json`) stores course/path **metadata** (not full
  modules) to stay small; `UpsertDoc` merges, so a prior Python run's fields are
  preserved.

Portal flags (`-A`/`-a`/`--public`, `-B`/`-b`/`--partner`, `--portal NAME`) and
URL inference (paste a full URL instead of an id) work on every command.

## Examples

```bash
# Sign in once (shared with the Python tool)
./csb login            # public
./csb login -B         # partner

# Regenerate Markdown offline (no browser)
./csb md -c 53
./csb md -B -p 4184

# Browse the local database
./csb list -B --courses
./csb search spanner -B --lab

# Fetch a lab end-to-end
./csb fetch -B -l 6523            # add --force to re-fetch, --headless to hide Chrome
```

## Layout

```
go/
  main.go
  internal/
    portal/    (portal, id) registry + URL/host inference
    textutil/  string helpers the Markdown output depends on
    model/     on-disk entity structs (+ order-preserving maps)
    mdgen/     Markdown generators (byte-parity with Python)
    store/     JSON + TinyDB database I/O, per-portal paths
    browser/   chromedp launcher (shared profile, anti-automation flags)
    scrape/    HTML parsers (offline-testable; lab done)
    cli/       command dispatch and the commands
```

## Verifying parity

The Go and Python `md` output is diffed in development like this:

```bash
# Python writes to csbmdvault/ ; point Go at a temp vault and diff.
uv run app/main.py md -c 53
CSB_VAULT=/tmp/govault go run ./go md -c 53
diff csbmdvault/public/courses/*.md /tmp/govault/public/courses/*.md
```

`CSB_DATA` and `CSB_VAULT` env vars override the data/vault roots (used for
isolated tests).

## What's next

The remaining work is the course/path fetch pipeline — metadata + outline
(`ql-contents-menu`), then per-activity content (video transcripts, quizzes,
`html_bundle` lessons, documents) and the path→courses→labs cascade. This is the
deepest part of the scraper and is best built while iterating against a live
signed-in session. See `../docs/rewrite-plan.md` for the overall plan.
