# Plan: Re-implementing as a Single Distributable App

Status: **proposal / not started.** This document weighs the options for
rebuilding the current Python + Selenium tool as a single, easy-to-distribute
binary (Rust or Go) or a desktop app (Electron/Tauri), and recommends a path.

## Why consider a rewrite

The Python version works, but distribution is the pain point:

- Users must install Python 3.12, `uv`, and the right dependencies.
- The `.webdriver_profiles/` + Chrome coupling is fiddly for non-technical users
  (exactly the audience the new Getting Started guide targets).
- "Download the repo, run `uv sync`, then `uv run …`" is a lot to ask of someone
  who just wants their course notes.

The dream: **hand someone one file (or one installer), they double-click, log
in, and fetch.**

## The one constraint that dominates everything

This is not a plain HTTP scraper. It fundamentally **drives a real, logged-in
Chrome browser** because:

1. Course/lab/path pages require an authenticated session.
2. Content is JavaScript-rendered (web components like `ql-contents-menu`,
   `ql-youtube-video`, `ql-quiz`) — there is no static HTML or public JSON API to
   hit with a bare HTTP client.
3. The site actively fingerprints automation, so we reuse a real browser profile
   and reduce automation signals.

**Any rewrite must keep browser automation.** That single fact drives the
language and packaging choice more than anything else. The realistic options are:

- **Drive the user's existing Chrome** (external dependency, small app), or
- **Bundle a browser engine** (self-contained, large app).

## What we'd have to port

| Piece | Today (Python) | Notes for a port |
|---|---|---|
| Browser automation | Selenium + Chrome profile | The core; see options below. |
| HTML parsing | BeautifulSoup | Every language has a good equivalent. |
| Data model | `Course` / `Path` / `Lab` + collections | Straightforward structs/enums. |
| Storage | TinyDB (JSON) + per-item JSON | Swap for SQLite or keep JSON files. |
| Markdown generation | string building + front-matter | Trivial to port. |
| Multi-portal logic | `PORTALS` registry, per-portal paths | Pure logic; ports cleanly. |
| CLI + interactive menu | argparse + `scraper.py` | `clap` (Rust) / `cobra` (Go) / GUI. |

The scraping/parsing selectors and the portal/id logic are the valuable,
hard-won parts — those port as data + logic regardless of language.

## Options

### Option A — Go (CLI-first single binary) ★ recommended for a CLI

- **Browser automation:** [`chromedp`](https://github.com/chromedp/chromedp)
  talks to Chrome directly over the DevTools Protocol — **no separate
  chromedriver needed**. [`go-rod`](https://github.com/go-rod/rod) is a strong
  alternative and can even download a Chromium for you.
- **HTML parsing:** `goquery` (jQuery-like, very close to BeautifulSoup ergonomics).
- **Storage:** SQLite (`modernc.org/sqlite`, pure-Go, no cgo) or plain JSON.
- **CLI:** `cobra` + `bubbletea` for a nice interactive TUI.
- **Distribution:** trivial static cross-compilation to macOS/Windows/Linux; a
  single ~10–20 MB binary.
- **Trade-off:** still requires Chrome installed (or auto-downloaded by go-rod).
  No native GUI unless you add a webview.

**Best when:** the goal is a small, fast, cross-platform CLI that's easy to ship.
This is the pragmatic sweet spot for the current tool.

### Option B — Rust (smallest, strictest binary)

- **Browser automation:** `thirtyfour` or `fantoccini` (WebDriver) or
  `chromiumoxide` (CDP, like chromedp).
- **HTML parsing:** `scraper` (built on `html5ever`).
- **Storage:** `rusqlite` (SQLite) or `serde_json`.
- **CLI:** `clap` + `ratatui` for a TUI.
- **Distribution:** smallest, fastest binary; excellent correctness guarantees.
- **Trade-off:** slower development velocity; the browser-automation crates are
  less turnkey than Go's `chromedp`. Still needs external Chrome/driver.

**Best when:** performance/footprint matter most and you're comfortable with Rust.
For this project the browser is the bottleneck, not CPU, so Rust's speed edge is
largely wasted — it's a fit only if you specifically want Rust.

### Option C — Electron (desktop GUI, self-contained browser)

- **Key advantage:** Electron *is* Chromium. It can **log the user in within a
  real window and scrape using that same session** — potentially removing the
  "you must have Chrome + a driver" dependency entirely, and giving non-technical
  users a click-to-log-in experience.
- **Storage/logic:** reuse in JS/TS; SQLite via `better-sqlite3`.
- **Distribution:** signed installers (.dmg/.exe) with auto-update.
- **Trade-off:** large (~100–150 MB), back to a JS/TS codebase, heavier build and
  code-signing/notarization pipeline.

**Best when:** the priority is a polished desktop app for non-technical users,
and binary size doesn't matter.

### Option D — Tauri (GUI middle ground) ★ recommended if we want a GUI

- Rust core + the OS's native webview for the UI → installers in the
  **~5–15 MB** range instead of Electron's ~100 MB+.
- Can embed a webview for the login flow and drive an external Chrome (via
  `chromiumoxide`) for scraping, or use the webview session directly.
- **Trade-off:** younger ecosystem than Electron; webview differs per-OS; still
  more moving parts than a pure CLI.

**Best when:** you want a real GUI for non-technical users without Electron's bulk.

## Comparison at a glance

| | Go (chromedp) | Rust | Electron | Tauri |
|---|---|---|---|---|
| Artifact | 1 binary | 1 binary | Installer | Installer |
| Size | ~10–20 MB | ~5–10 MB | ~100–150 MB | ~5–15 MB |
| Needs external Chrome | Yes* | Yes | **No** (bundled) | Usually |
| GUI for non-tech users | TUI only | TUI only | **Yes** | **Yes** |
| Browser automation maturity | **Excellent** | Good | N/A (native) | Good |
| Dev velocity | High | Medium | Medium | Medium |
| Cross-compile ease | **Excellent** | Good | Per-OS build | Per-OS build |

\* `go-rod` can auto-download a Chromium, softening this.

## Recommendation

Two viable directions depending on the primary audience:

1. **If the tool stays CLI-first → rewrite in Go with `chromedp`.** Best
   browser-automation story, zero extra driver, tiny static binary, trivial
   cross-compilation. Lowest-risk, highest-leverage rewrite of the current tool.

2. **If the priority is a click-and-go app for non-technical users → Tauri**
   (preferred over Electron for size), using an embedded webview for login and a
   CDP client for scraping. Electron only if bundling Chromium to eliminate the
   external-Chrome dependency outweighs the ~100 MB size.

A pragmatic sequence: **do the Go CLI first** (proves the port, keeps the tool
usable), then optionally wrap a Tauri GUI around the same core later.

## Suggested phased plan (Go path)

1. **Spike** — one course fetch end-to-end in Go: `chromedp` login using an
   existing profile → fetch `course_templates/<id>` → parse `ql-contents-menu`
   → emit the same Markdown. Validates the hardest 20%.
2. **Core model** — port `Course`/`Path`/`Lab` + the `PORTALS` registry and
   id/portal inference. Reuse this repo's selectors verbatim.
3. **Storage** — SQLite (or JSON to mirror today) with the same per-portal
   scoping and shared `materials/` layout.
4. **Cascade + flags** — path → courses → labs, `--force`, `--toc`,
   `--no-transcript`, `--headless`, portal flags. Match the current CLI surface
   so docs barely change.
5. **Interactive TUI** — `bubbletea` menu mirroring `scraper.py`.
6. **Parity + cutover** — diff Go output against the Python output on a set of
   known ids until byte-comparable, then ship binaries via GitHub Releases.

Keep the Python version as the reference implementation until Go reaches parity.

## Risks & open questions

- **Bot detection parity** — the Python version's anti-detection tweaks
  (`--headless=new`, disabling `AutomationControlled`, profile reuse) must be
  reproduced; CDP-based tools have their own fingerprinting quirks to manage.
- **Login UX** — a CLI still needs the "open a window, log in, come back" step
  unless we go the Tauri/Electron embedded-webview route.
- **Site drift** — the selectors change periodically (this repo has already
  survived cloudskillsboost.com → skills.google → partner portal). Whatever the
  language, keep selectors centralized and easy to patch.
- **Scope** — is the goal purely easier distribution (CLI/Go is enough) or a
  genuine consumer desktop app (Tauri/Electron)? That answer picks the option.
