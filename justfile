# Google Skills Scraper — task runner (https://just.systems). Run `just` to list recipes.
#
# Quick start:
#   brew install just        # one-time (macOS); see just.systems for others
#   just setup               # one-time: install the Tauri CLI
#   just dev                 # build the skills-scraper binary + launch the desktop app

# Show the available recipes.
default:
    @just --list

# Build the skills-scraper Go binary at the repo root (what the GUI shells out to). The
# .bin extension keeps build artifacts out of git via a single `*.bin` ignore.
cli:
    cd go && go build -o ../skills-scraper.bin .

# Launch the desktop app (Google Skills Scraper). Rebuilds the CLI first.
dev: cli
    cd gui/src-tauri && cargo tauri dev

# Package a distributable, standalone desktop app (.app/.dmg, etc.). Builds the
# Go binary as a Tauri sidecar named with the Rust target triple (what
# externalBin expects), so the shipped .app carries its own skills-scraper and
# runs with no repo checkout. The theme/ folder is bundled as a resource.
bundle:
    #!/usr/bin/env bash
    set -euo pipefail
    triple=$(rustc -Vv | sed -n 's/host: //p')
    echo "Building skills-scraper sidecar for ${triple}…"
    mkdir -p gui/src-tauri/binaries
    ( cd go && go build -o "../gui/src-tauri/binaries/skills-scraper-${triple}" . )
    cd gui/src-tauri && cargo tauri build

# Run the CLI directly, e.g. `just run fetch -A -p 20` or `just run list -B -c`.
run *ARGS: cli
   ../skills-scraper.bin {{ARGS}}

# Go vet + tests.
test:
    cd go && go vet ./... && go test ./...

# One-time: install the Tauri v2 CLI (cargo subcommand).
setup:
    cargo install tauri-cli --version '^2.0' --locked

# Preview just the GUI frontend in a browser (no Tauri runtime; buttons inert).
web:
    @echo "Serving gui/src at http://localhost:5599 (Ctrl-C to stop)"
    cd gui/src && python3 -m http.server 5599
