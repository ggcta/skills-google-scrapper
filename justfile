# CSB — task runner (https://just.systems). Run `just` to list recipes.
#
# Quick start:
#   brew install just        # one-time (macOS); see just.systems for others
#   just setup               # one-time: install the Tauri CLI
#   just dev                 # build the csb binary + launch the desktop app

# Show the available recipes.
default:
    @just --list

# Build the csb Go binary at the repo root (what the GUI shells out to).
cli:
    cd go && go build -o ../csb .

# Launch the desktop app (CSB Studio). Rebuilds the CLI first.
dev: cli
    cd gui/src-tauri && cargo tauri dev

# Package a distributable desktop app (.app/.dmg, etc.). Rebuilds the CLI first.
bundle: cli
    cd gui/src-tauri && cargo tauri build

# Run the CLI directly, e.g. `just run fetch -A -p 20` or `just run list -B -c`.
run *ARGS: cli
    ./csb {{ARGS}}

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
