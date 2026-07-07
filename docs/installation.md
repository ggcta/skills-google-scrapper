# Installation

> Not a developer? The **[Getting Started guide](getting-started.md)** covers
> installation in plain language, including how to install `git` and `uv`.

The app is run with **[uv](https://docs.astral.sh/uv/)**, which manages the
virtual environment and dependencies for you. You do **not** need to create a
`venv` or run `pip` by hand.

## Prerequisites

- **Python 3.12+**
- **uv** — install it from <https://docs.astral.sh/uv/getting-started/installation/>
- **Google Chrome** — the scraper drives a real Chrome browser via Selenium.

## 1. Clone the repo

```sh
git clone https://github.com/samdx/cloudskillsboost-helper.git
cd cloudskillsboost-helper
```

## 2. Install dependencies

```sh
uv sync
```

This reads `pyproject.toml` / `uv.lock`, creates a `.venv` automatically, and
installs everything. Re-run it any time you pull new changes.

## 3. Run the app

You never activate the virtualenv manually — prefix commands with `uv run`:

```sh
# Show all commands
uv run app/main.py --help

# Launch the interactive menu
uv run app/main.py interactive
```

See **[usage.md](usage.md)** for the full command reference.

## Optional configuration

App-wide settings live in `app/config/settings.py`, including:

- `OUTPUT_FOLDER_NAME` — where Markdown is written (default: `csbmdvault/`)
- `DATA_FOLDER_NAME` — where the database and JSON backups live (default: `data/`)
- `WEBDRIVER_PROFILE_FOLDER_NAME` — the reusable Chrome profile that stores your
  login session (default: `.webdriver_profiles/`)
- `DEFAULT_PORTAL` — `public` or `partner`

The `data/` and `csbmdvault/` folders are created automatically on first run.

## Run with Docker (web UI only)

A small Flask web UI for browsing downloaded content:

```sh
docker build -t csbhelper .
docker run -dp 8080:8080 csbhelper
# open http://localhost:8080
```

> The Docker image serves the browsing UI. Scraping itself is meant to be run
> locally with `uv run`, because it drives a Chrome window you log in to.

## Legacy setup scripts

Older `setup_env.sh` / `pip install -r requirements.txt` / `pipenv` flows still
exist for reference, but **`uv sync` is the supported path** and supersedes them.
