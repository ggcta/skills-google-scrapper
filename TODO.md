## TODO

- [x] Create the `data` folder if it does not exist to avoid the below `FileNotFoundError` error.

```bash
$ uv run app/main.py list

Launching browser for list extraction...
Reloading paths list from remote...
Closing browser...
Traceback (most recent call last):
  File "/Users/samdinh/repos/csbhelper/app/main.py", line 379, in <module>
    main()
  File "/Users/samdinh/repos/csbhelper/app/main.py", line 376, in main
    args.func(args)
  File "/Users/samdinh/repos/csbhelper/app/main.py", line 41, in cmd_list
    collection.load_json()
  File "/Users/samdinh/repos/csbhelper/app/models/collection.py", line 72, in load_json
    db = Database()
         ^^^^^^^^^^
  File "/Users/samdinh/repos/csbhelper/app/services/database.py", line 12, in __new__
    cls._instance._initialize()
  File "/Users/samdinh/repos/csbhelper/app/services/database.py", line 19, in _initialize
    self.db = TinyDB(self.db_path, indent=2, encoding='utf-8')
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/samdinh/repos/csbhelper/.venv/lib/python3.12/site-packages/tinydb/database.py", line 94, in __init__
    self._storage: Storage = storage(*args, **kwargs)
                             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/samdinh/repos/csbhelper/.venv/lib/python3.12/site-packages/tinydb/storages.py", line 113, in __init__
    touch(path, create_dirs=create_dirs)
  File "/Users/samdinh/repos/csbhelper/.venv/lib/python3.12/site-packages/tinydb/storages.py", line 32, in touch
    with open(path, 'a'):
         ^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/Users/samdinh/repos/csbhelper/data/database.json'
```

- [x] Migrate to `uv` package management tool.
- [x] Command-line interface (`uv run app/main.py …`).
- [x] Partner portal support ([partner.skills.google](https://partner.skills.google/)) — shipped in v2.1.0.
- Do not over-write the existing Markdown files, it's actually up to you, as a user.
- Call to Gemini/LLAMA or any other LLM for helping summarize/re-formatting the transcripts.
   + For time being, Gemini for me, is not so good so I don't use yet.
   + LM Studio is a good choice with LLAMA 3.1, 3.2 but my machine is not suitable for running this continously.

Check [CONTRIBUTION](CONTRIBUTION.md) for more.

- [ ] TODO: Sync the data folder to a GCS bucket: `gcloud storage rsync --recursive data/ gs://csbhelper/`

## v3.0.0 — Multi-vendor + complete rebrand (planned)

**Why:** the tool is currently Google-specific (skills.google). The scraping
model — *portals* that expose courses / paths / labs and turn them into a
Markdown knowledge base — generalizes to other vendors, so 3.0.0 should become a
**vendor-neutral learning-portal scraper**. That makes the current "Google Skills
Scraper" name too narrow, and it's the right moment to do the *complete* rebrand
we deferred in v2.2.0 (which only renamed user-facing text + the binary).

- [ ] **Multi-vendor portal support.** Generalize `internal/portal` (currently
      `public`/`partner` under one base) into a vendor→portal registry. Candidate
      vendors: AWS (Skill Builder), Microsoft/Azure (Microsoft Learn), Alibaba
      Cloud Academy, plus the existing Google Skills. Each vendor needs its own
      base URLs, catalog API shape, auth/login flow, and page parsers. Keep the
      shared model (Path/Course/Lab → Markdown) and per-vendor storage roots
      (`data/<vendor>/<portal>/…`). Design the parser layer so a new vendor is a
      pluggable module, not a fork.
- [ ] **Pick a vendor-neutral name** (needed once it's multi-vendor). Ideas —
      recommend **SkillVault** (skills across vendors → your Obsidian vault;
      binary `skillvault`); alternates: `LearnVault`, `CourseVault`, `SkillScribe`.
      Decision is open — this is the blocker for the rename below.
- [ ] **Complete/deep rebrand** (the internal identifiers kept as codenames in
      v2.2.0): Go module `csb` → new name (touches all `csb/internal/...`
      imports), Rust crate `csb-gui`, the `CSB_*` env vars
      (`CSB_DATA`/`CSB_VAULT`/`CSB_BIN`/`CSB_PROJECT_ROOT` → new prefix, keep the
      old names as deprecated aliases for one release), and the on-disk dirs
      (`csbmdvault/`, and if vendors get their own roots, restructure `data/`).
- [ ] **Data migration.** Renaming/​restructuring the data + vault dirs must ship
      a migration (or back-compat read of the old layout) so existing scraped
      content isn't orphaned — 2.2.0 explicitly avoided this by keeping the dirs.
- [ ] **Docs + versioning.** Bump to 3.0.0 across pyproject / tauri.conf.json /
      crate; rewrite READMEs and `docs/` around the multi-vendor model.
