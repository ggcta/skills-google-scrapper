# Usage

All commands run as:

```bash
uv run app/main.py <command> [options]
```

There are two ways to drive the app — a **command line** and an **interactive
menu**. They share the same underlying logic, so anything you can do in one you
can do in the other.

## First run

Most pages require you to be signed in, and no data ships with the app. So:

```bash
# 1. Sign in (a browser opens; log in, then press Enter)
uv run app/main.py login          # add -B for the partner portal

# 2. Build the catalog of paths (only needed if you want to browse/list paths)
uv run app/main.py list --reload --paths
```

You can skip step 2 if you already know the ID (or URL) of what you want and
just `fetch` it directly.

## Portals

Every data command works against one portal at a time. Default is **public**.

| Flag | Portal |
|---|---|
| `-A` / `-a` / `--public` | Public — `www.skills.google` (default) |
| `-B` / `-b` / `--partner` | Partner — `partner.skills.google` |
| `--portal <name>` / `-P` | Explicit name (advanced) |

Or paste a **full URL** in place of an ID and the portal is detected from the
host automatically.

## Commands

### `fetch` (alias `f`) — scrape content

```bash
uv run app/main.py fetch -p <id...>   # path(s)  → cascades to courses → labs
uv run app/main.py fetch -c <id...>   # course(s) → cascades to their labs
uv run app/main.py fetch -l <id...>   # lab(s)
```

Options:

| Option | Effect |
|---|---|
| `--force` / `-f` | Re-scrape even if already stored (applies down the tree). |
| `--toc` / `-t` | Table of contents / structure only. |
| `--no-transcript` | Keep everything except video transcripts. |
| `--no-md` | Update the database only; don't write Markdown. |
| `--headless` | Run Chrome without a visible window. |
| portal flags | `-A` / `-B` / `--portal` as above. |

Examples:

```bash
uv run app/main.py fetch -p 16                 # public path + everything under it
uv run app/main.py fetch -c 53 1145 --toc      # two courses, outline only
uv run app/main.py fetch -B -p 4343            # a partner path
uv run app/main.py fetch -c https://partner.skills.google/course_templates/35
```

#### Bulk fetch everything — `fetch --all`

A power-user option (hidden from `--help`, but fully supported) refreshes the
catalog from the site, then scrapes every item it finds. `--all` takes an
optional kind — `paths` (the default), `courses`, `labs`, or `all`:

```bash
uv run app/main.py fetch --all              # every public path (cascades to its courses + labs)
uv run app/main.py fetch --all -B           # every partner path
uv run app/main.py fetch --all courses      # every standalone course
uv run app/main.py fetch --all all --headless   # paths + courses + labs, no window
csb fetch --all                             # same, via the Go binary
```

Because paths cascade to their courses and labs, plain `fetch --all` already
pulls almost the entire portal; `--all all` additionally sweeps any standalone
courses/labs not reachable from a path. Combine with `-f`/`--force` to re-scrape
items you already have. This can take a long time and drive a lot of traffic —
prefer `--headless` and expect it to run for a while.

### `list` (alias `l`) — see what you have

```bash
uv run app/main.py list --paths       # default
uv run app/main.py list --courses
uv run app/main.py list --labs
```

- `--reload` / `-r` — refresh the list from the website first (opens a browser).
- `--id` / `-i` or `--name` / `-n` — sort order.
- `--headless` — reload without a visible browser window.
- portal flags — e.g. `list -B --courses`.

### `search` (alias `s`) — query the local database

```bash
uv run app/main.py search "kubernetes"
uv run app/main.py search "networking" --course      # limit to courses
uv run app/main.py search "gke" --field title        # limit to one field
```

Add a portal flag to search the partner database instead.

### `md` — (re)generate Markdown from stored data

No browser needed; works offline from what you've already fetched.

```bash
uv run app/main.py md -c 53,1145        # comma-separated IDs
uv run app/main.py md -p 16 --toc
uv run app/main.py md -l 104653
```

### `interactive` (alias `i`) — guided menu

```bash
uv run app/main.py interactive
```

```
AVAILABLE OPTIONS  (working portal: public)
  1. f: FETCH content (path / course / lab)
  2. l: LIST paths / courses / labs
  3. s: SEARCH the database
  4. m: GENERATE markdown
  5. w: LAUNCH browser (manual login)
  6. p: SWITCH portal (public / partner)
  0. q: QUIT
```

The working portal is shown in the header and persists for the session; switch
it with option **6**. Fetch prompts also let a pasted URL override the portal
per item.

### `login` — sign in to a portal

```bash
uv run app/main.py login          # public
uv run app/main.py login -B       # partner
```

Opens a browser at the portal's home page. Log in, then press **Enter** to close
it. Your session is saved to the reusable Chrome profile, so later fetches are
already authenticated. Run it again whenever pages start returning empty.

### `browser` (aliases `b`, `w`) — manual browser

Opens a Chrome window (with the shared profile) for manual login or debugging,
and keeps it open until you press Enter.

## Where output goes

| Path | Contents |
|---|---|
| `csbmdvault/<portal>/{courses,paths,labs}/*.md` | Your Markdown notes. Open the vault in Obsidian. |
| `csbmdvault/materials/courses/<id>/…` | Downloaded documents (shared across portals). |
| `data/<portal>/database.json` | The TinyDB database. |
| `data/<portal>/{courses,paths,labs}/*.json` | Per-item JSON backups. |
