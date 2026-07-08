# CSB Studio — desktop GUI (Tauri)

A thin [Tauri](https://tauri.app) desktop shell over the `csb` Go binary. Every
action shells out to `csb` (see `src-tauri/src/main.rs`), so the GUI inherits the
CLI's byte-for-byte-verified behaviour and never reimplements scraping logic.

```
gui/
  src/            frontend (vanilla HTML/CSS/JS, no bundler)
    index.html
    styles.css
    main.js
  src-tauri/      Rust shell
    src/main.rs   Tauri commands: list_items, search_items, fetch, login, …
    tauri.conf.json
    Cargo.toml
    icons/        placeholder (replace before `tauri build`)
```

## Prerequisites

- **Rust** (the workspace uses cargo/rustc 1.9x).
- The **`csb` binary** built and reachable (see below).
- **Google Chrome** (the fetch/login commands drive it, via `csb`).

The frontend has no build step (plain HTML/JS), so Node is optional — the Tauri
CLI can run via cargo.

## Build the `csb` binary first

The GUI resolves the binary in this order: `CSB_BIN` env → `<repo-root>/csb` →
`csb` on `PATH`. The simplest setup drops it at the repo root:

```bash
cd go && go build -o ../csb . && cd ..
```

It also runs `csb` with the working directory set to the repo root (detected by
walking up for a checkout containing `.git` and `go/`, or `CSB_PROJECT_ROOT`), so
it reads/writes the same `data/` and `csbmdvault/` as the CLI.

## Run in development

The project ships a [`justfile`](../justfile) (a modern task runner) so you don't
have to remember the multi-step dance:

```bash
brew install just     # one-time (macOS); see https://just.systems for other OSes
just setup            # one-time: install the Tauri v2 CLI
just dev              # builds the csb binary, then launches the desktop app
```

`just dev` runs `go build -o ./csb ./go` and then `cargo tauri dev` for you.
Other recipes: `just run <args>` (CLI), `just bundle` (package), `just test`.

<details><summary>Manual equivalent (no <code>just</code>)</summary>

```bash
cargo install tauri-cli --version '^2.0'   # one-time
cd go && go build -o ../csb . && cd ..      # build the binary the GUI calls
cd gui/src-tauri && cargo tauri dev
```
</details>

`cargo build` (what CI/verification runs) compiles the Rust shell; `cargo tauri
dev` opens the actual window.

## Build a distributable

```bash
just bundle
# or: cd gui/src-tauri && cargo tauri build   # .app/.dmg (macOS), .exe/.msi (Windows), …
```

> Replace `icons/icon.png` (currently a 1×1 placeholder) with real icons before
> bundling — e.g. `cargo tauri icon path/to/1024.png`.

## What it does

- **Portal toggle** (Public / Partner) applies to every action.
- **Fetch** — path / course / lab by ID or URL, with force / TOC-only /
  no-transcripts / headless options; live output streams into the console.
- **Browse** — list stored paths / courses / labs (`csb list --json`).
- **Search** — query the local database (`csb search --json`).
- **Sign in** — opens a browser via `csb login`; click *Done* when finished.
- **Open vault** — reveals `csbmdvault/` in the OS file manager.

## How it talks to `csb`

The read commands use `csb … --json` (clean JSON on stdout, status on stderr).
`fetch` streams stdout/stderr line-by-line to the UI via Tauri events
(`fetch-log`, `fetch-done`). `login` keeps the child process open until the
*Done* button triggers `finish_login`.
