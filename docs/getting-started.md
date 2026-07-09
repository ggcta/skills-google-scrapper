# Getting Started (Non-Technical Walkthrough)

This guide gets you from **zero to a folder full of course notes** without
assuming you're a developer. Follow it top to bottom. Each step is a single
copy‑paste command.

Everything you download is saved on **your own computer** — nothing is uploaded
anywhere.

---

## What you'll need (once)

1. **A Google Skills account** — the same one you use at
   [skills.google](https://www.skills.google). You need to be able to sign in,
   because most course pages are only visible to logged-in users.
2. **Google Chrome** installed. The tool opens a real Chrome window to read the
   pages, just like you would by hand.
3. **Two small free tools**: `git` and `uv`. Install steps are below.

You only do this setup **once**.

### Install the tools

- **macOS** — open the **Terminal** app and paste:

  ```bash
  # Installs Homebrew if you don't have it, then git + uv
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  brew install git uv
  ```

- **Windows** — open **PowerShell** and paste:

  ```powershell
  winget install Git.Git
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

- **Linux** — use your package manager for `git`, then:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

> Not sure if it worked? Type `git --version` and `uv --version`. If each prints
> a version number, you're good.

### Download the app

Pick a folder you'll remember (your home folder is fine) and run:

```bash
git clone https://github.com/samdx/cloudskillsboost-helper.git
cd cloudskillsboost-helper
uv sync
```

`uv sync` downloads everything the app needs into its own private space — it
won't touch the rest of your computer.

> **From now on, always run commands from inside this `cloudskillsboost-helper`
> folder.** If you close the terminal, reopen it and type `cd
> cloudskillsboost-helper` first.

---

## Step 1 — Sign in (once per session)

```bash
uv run app/main.py login
```

A Chrome window opens. **Log in to Google Skills like you normally
would.** When you're done and can see your dashboard, come back to the terminal
and press **Enter**. The window closes and your login is remembered for next
time.

Using the **partner portal** (`partner.skills.google`)? Sign in to that one too:

```bash
uv run app/main.py login -B
```

---

## Step 2 — The easy way: the menu

If you'd rather not remember commands, run:

```bash
uv run app/main.py interactive
```

You'll get a simple numbered menu:

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

- Type **1** to **fetch** something. It will ask what to grab (a path, a course,
  or a lab) and for the ID or URL — then it does the rest.
- Type **6** to switch between the **public** and **partner** portals.
- Type **0** to quit.

That's genuinely all you need. The rest of this guide is for when you want to
type commands directly.

---

## Step 3 — Finding the ID of what you want

Open the course, path, or lab in your browser and look at the address bar. The
number at the end is the **ID**:

| You're looking at | Example URL | ID |
|---|---|---|
| A **path** | `https://www.skills.google/paths/16` | `16` |
| A **course** | `https://www.skills.google/course_templates/53` | `53` |
| A **lab** | `https://www.skills.google/focuses/104653?...` | `104653` |

**Tip:** you don't even have to find the ID — you can paste the **whole URL**
into any command and the tool figures out the rest (including which portal it
came from).

---

## Step 4 — Download some content

Grab an entire learning path — this pulls the path, every course in it, and
every lab automatically:

```bash
uv run app/main.py fetch -p 16
```

Other things you can grab:

```bash
# Just one course
uv run app/main.py fetch -c 53

# Just one lab
uv run app/main.py fetch -l 104653

# Something from the partner portal (note the -B)
uv run app/main.py fetch -B -p 4343

# Or paste a full URL — no ID hunting, no portal flag needed
uv run app/main.py fetch -c https://partner.skills.google/course_templates/35
```

A Chrome window opens and works through the pages. **Leave it alone while it
runs** — it may scroll and click on its own. When it finishes, the window closes
by itself.

Handy extras (add them to the end of a `fetch` command):

- `--toc` — grab just the outline/table of contents, skip the long transcripts.
- `--force` — re-download something you already have (to pick up updates).
- `--headless` — do it all without a visible browser window.

---

## Step 5 — Read your notes

Everything lands in the **`csbmdvault`** folder inside the app folder:

```
csbmdvault/
  public/         ← content from www.skills.google
    courses/      ← one Markdown file per course
    paths/
    labs/
  partner/        ← content from partner.skills.google
  materials/      ← any documents that were attached to courses
```

These are plain **Markdown (`.md`) files** — open them in any text editor.

For the best experience, install **[Obsidian](https://obsidian.md)** (free) and
open the `csbmdvault` folder as a "vault". You'll get a nicely formatted,
searchable, linked view of everything you've collected.

---

## Doing more without re-downloading

Once content is saved, these are instant (no browser needed):

```bash
# See everything you've downloaded
uv run app/main.py list --courses

# Search your notes for a word
uv run app/main.py search kubernetes

# Rebuild the Markdown for a course (e.g. after an app update)
uv run app/main.py md -c 53
```

---

## Common questions

**Do I have to log in every time?**
Your login is remembered between runs. If pages start coming back empty or you
get redirected to a sign-in screen, just run `uv run app/main.py login` again.

**It opened a browser and I panicked / closed it.**
No harm done. Just run the command again.

**"No paths found locally."**
You haven't built the catalog yet. Run
`uv run app/main.py list --reload --paths` once to fetch the list of paths, or
simply `fetch` a specific ID directly — you don't need the catalog to fetch by
ID/URL.

**Which portal am I on?**
Commands default to **public**. Add `-B` for partner. In the interactive menu,
the current portal is shown at the top and you switch it with option **6**.

**Is this against the rules?**
Only download content **you already have access to**, for your own study, and
keep it reasonable. Don't redistribute what you scrape. See the note at the
bottom of the [README](../README.md).

---

Stuck on something not covered here? Open an issue on the repository — see
[CONTRIBUTION.md](../CONTRIBUTION.md).
