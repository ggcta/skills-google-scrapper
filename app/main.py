#!/usr/bin/env python3
import sys
import os
import argparse
from config.settings import WEBDRIVER_PROFILE_FOLDER_NAME, DEFAULT_PORTAL, PORTALS, portal_config, DATA_FOLDER_NAME

# Ensure app modules can be imported
# Add 'app' directory to sys.path so we can import 'models' directly
sys.path.append(os.path.join(os.getcwd(), 'app'))

from models.course import Course
from models.lab import Lab
from models.path import Path
from models.paths import Paths
from models.courses import Courses
from models.labs import Labs
from services.launch_browser import launch_browser
from services import browser_endpoint
from utils.utils import util_portal_and_id, util_ensure_authenticated
from utils.completeness import item_complete, path_complete, course_complete


def _resolve_portal(raw, default_portal):
    """
    Resolve a raw fetch target (bare id or full URL) into (portal, id).
    A URL's host determines the portal and overrides the default.
    """
    inferred_portal, ident = util_portal_and_id(raw)
    return (inferred_portal or default_portal), ident


def _stored_name(portal, table, ident):
    """
    Return a stored item's display name from the database (or '' if unknown),
    so fetch progress lines can read "<id> - <name>" instead of a bare id.
    """
    try:
        from services.database import Database
        doc = Database(portal).get(table, ident)
        if doc:
            return doc.get('name') or doc.get('title') or ''
    except Exception:
        pass
    return ''


def _fetch_label(portal, table, ident):
    """Format an item as "<id> - <name>" when the name is known, else "<id>"."""
    name = _stored_name(portal, table, ident)
    return f"{ident} - {name}" if name else str(ident)


def _reusable_browser():
    """
    Backlog #14: return the debug port of a live, reusable persistent browser, or
    None. A separate `browser` process advertises it; fetch/list ATTACH to that
    already-signed-in Chrome instead of launching (and re-authenticating) their
    own — and so they don't lock the shared profile twice.
    """
    port, ok = browser_endpoint.load_endpoint()
    if ok and browser_endpoint.endpoint_alive(port):
        return port
    return None


def _acquire_driver(headless):
    """
    Return (driver, borrowed). Reuse the persistent browser (#14) when one is
    live — attach to it so the sign-in carries over; otherwise launch a fresh
    browser on the shared profile.
    """
    port = _reusable_browser()
    if port is not None:
        try:
            print("\n\033[35mReusing the open browser...\033[0m")
            return launch_browser(browser="chrome",
                                  debugger_address=f"127.0.0.1:{port}"), True
        except Exception as e:
            print(f"(reuse) could not attach to the open browser: {e}; launching a new one.")
    print("\n\033[35mLaunching browser...\033[0m")
    return launch_browser(headless=headless, browser="chrome",
                          profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME), False


def _release_driver(driver, borrowed):
    """
    Tear a driver down. A borrowed (attached) driver only DETACHES — quitting it
    ends our chromedriver session but leaves the shared browser running, because
    ChromeDriver only closes a Chrome it launched itself.
    """
    if not driver:
        return
    print("Detaching from the open browser..." if borrowed else "Closing browser...")
    driver.quit()


def add_portal_flags(parser):
    """
    Add shorthand portal-selection flags to a subparser, so callers can avoid
    the verbose ``--portal <name>`` form:

        -A / -a / --public   -> public portal (default)
        -B / -b / --partner  -> partner portal

    ``--portal/-P <name>`` is kept for scripting/explicitness. All are mutually
    exclusive and resolve to ``args.portal``.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-A', '-a', '--public', dest='portal', action='store_const', const='public',
                       help='Use the public portal (default)')
    group.add_argument('-B', '-b', '--partner', dest='portal', action='store_const', const='partner',
                       help='Use the partner portal')
    group.add_argument('--portal', '-P', dest='portal', choices=list(PORTALS.keys()),
                       help='Explicit portal name (advanced)')
    parser.set_defaults(portal=DEFAULT_PORTAL)


def _fetch_and_save_lab(lid, driver, portal, force, no_md, toc_only, fetch_url=None):
    """
    Fetch a single lab and persist it (JSON, markdown, and the labs collection).
    Returns the Lab if fetched, or None if it was skipped (already stored).

    fetch_url, when given, overrides the lab's default catalog URL — used for
    partner labs, which are served from a parent-referencing focus URL.
    """
    lab = Lab(id=lid, driver=driver, portal=portal)
    # fetch_data scrapes the lab's page (name, description, steps).
    # Honors force: skips if already stored unless force is set.
    if not lab.fetch_data(force=force, fetch_url=fetch_url):
        return None

    lab.save_json()  # Backs up to file and syncs to DB
    if not no_md:
        lab.save_markdown(toc_only=toc_only)

    # Keep the labs collection in sync (same portal).
    labs_collection = Labs(portal=portal)
    labs_collection.load_json()
    labs_collection.collection[lab.id] = lab.name
    labs_collection.save_json()
    return lab

def cmd_list(args):
    """Handle list command"""

    portal = getattr(args, 'portal', DEFAULT_PORTAL)
    headless = getattr(args, 'headless', False)

    # Determine type
    if args.courses:
        target_class = Courses
        label = "courses"
    elif args.labs:
        target_class = Labs
        label = "labs"
    else:
        # Default to paths or if args.paths is set
        target_class = Paths
        label = "paths"

    # Reload from remote first, if requested.
    if args.reload:
        driver = None
        borrowed = False
        try:
            driver, borrowed = _acquire_driver(headless)

            print(f"Reloading {label} list from remote [{portal}]...")
            collection = target_class(driver=driver, portal=portal)
            collection.load_json()

            # Fetch list (each collection exposes a fetch_<label> method)
            try:
                method_name = f"fetch_{label}"
                fetch_method = getattr(collection, method_name, None)
                if fetch_method:
                    if fetch_method(force=True):  # reload implies force
                        print(f"{label.capitalize()} list updated.")
                    else:
                        print(f"Failed to update {label} list.")
                else:
                    print(f"Reload not supported for {label}.")
            except Exception as e:
                print(f"Error reloading {label}: {e}")
        finally:
            _release_driver(driver, borrowed)

    print(f"Listing all {label} [{portal}]...")

    # Instantiate and load (reload might have updated DB)
    collection = target_class(portal=portal)
    collection.load_json()

    # Check if empty (only for Paths/Courses mostly)
    if not collection.collection:
        print(f"No {label} found locally.")
        if label == 'paths' and not args.reload:
             print("Use 'list -r -p' to fetch paths list.")
        elif label == 'courses' and not args.reload:
             print("Use 'list -r -c' to fetch courses list.")
        else:
             return

    # Determine sort
    sort_by = 'id' if args.id else 'name'

    collection.print_list(sort_by=sort_by)

def _kind_tables(kind):
    """Map a --all KIND argument to the catalog tables to sweep, or None."""
    k = (kind or '').strip().lower()
    if k in ('', 'path', 'paths', 'p'):
        return ['paths']
    if k in ('course', 'courses', 'c'):
        return ['courses']
    if k in ('lab', 'labs', 'l'):
        return ['labs']
    if k in ('all', 'everything', '*'):
        return ['paths', 'courses', 'labs']
    return None

def _collect_all_ids(kind, portal, headless):
    """Refresh the requested catalog(s) from the site and return their stored ids.

    Returns a dict {table: [id, ...]} for the tables implied by KIND. Reloading
    is best-effort: on failure we fall back to whatever is already stored.
    """
    tables = _kind_tables(kind)
    if tables is None:
        print(f"Unknown kind '{kind}' for --all (use paths, courses, labs, or all).")
        return {}

    class_map = {'paths': Paths, 'courses': Courses, 'labs': Labs}
    out = {}
    driver = None
    borrowed = False
    try:
        driver, borrowed = _acquire_driver(headless)
        for table in tables:
            collection = class_map[table](driver=driver, portal=portal)
            collection.load_json()
            try:
                fetch_method = getattr(collection, f"fetch_{table}", None)
                if fetch_method:
                    print(f"Reloading {table} list from remote [{portal}]...")
                    fetch_method(force=True)
            except Exception as e:
                print(f"warning: could not refresh {table} catalog: {e}")
            collection.load_json()
            out[table] = list(collection.collection.keys())
            print(f"{table}: {len(out[table])} to fetch [{portal}]")
    finally:
        _release_driver(driver, borrowed)
    return out

def _section_needs_browser(ids, kind, default_portal, force):
    """
    Browser-launch gate (backlog #7/#8): report whether this fetch section needs
    the browser at all — True when forcing, or when any requested id is not yet
    complete. When it returns False, cmd_fetch skips the section without ever
    launching the browser.
    """
    if force:
        return True
    for raw in ids:
        portal, ident = _resolve_portal(raw, default_portal)
        if not item_complete(portal, kind, ident):
            return True
    return False


def _proactive_signin(portal, headless):
    """
    Backlog #11: open the sign-in page and wait for the user before fetching.
    Launches a browser, navigates to <base>/users/sign_in, and loops until the
    user has signed in (util_ensure_authenticated). The session is saved to the
    browser profile, so the subsequent per-section fetches reuse it. If already
    signed in, the site redirects away and this returns immediately.
    """
    if headless:
        print("warning: --signin needs a visible browser window to sign in; drop --headless.")
    sign_in_url = portal_config(portal)["base"] + "/users/sign_in"
    driver = None
    try:
        print("\n\033[35mLaunching browser to sign in...\033[0m")
        driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
        print(f"Opening sign-in page: {sign_in_url}")
        driver.get(sign_in_url)
        util_ensure_authenticated(driver, sign_in_url, "")
    except Exception as e:
        print(f"(signin) Error during sign-in: {e}")
    finally:
        if driver:
            print("Closing sign-in browser...")
            driver.quit()


def cmd_fetch(args):
    """Handle fetch (scrape) command"""
    force = args.force
    no_md = args.no_md
    toc_only = args.toc
    no_transcript = args.no_transcript
    signin = getattr(args, 'signin', False)
    default_portal = getattr(args, 'portal', DEFAULT_PORTAL)
    headless = getattr(args, 'headless', False)

    fetch_paths_ids = args.paths
    fetch_courses_ids = args.courses
    fetch_labs_ids = args.labs

    # Hidden bulk mode: --all [paths|courses|labs|all] refreshes the catalog(s)
    # from the site then fetches every stored item. Paths cascade to their
    # courses and labs, so the default (paths) already pulls almost everything.
    all_kind = getattr(args, 'all', None)
    if all_kind is not None:
        collected = _collect_all_ids(all_kind, default_portal, headless)
        if collected.get('paths'):
            fetch_paths_ids = collected['paths']
        if collected.get('courses'):
            fetch_courses_ids = collected['courses']
        if collected.get('labs'):
            fetch_labs_ids = collected['labs']

    # Validation
    if not (fetch_paths_ids or fetch_courses_ids or fetch_labs_ids):
        print("Please specify items to fetch using -p <id>, -c <id>, or -l <id>.")
        return

    # #11: proactively sign in before fetching. The session persists in the
    # browser profile, so the per-section fetches below reuse it. #14: if a
    # reusable browser is already open, sign in there instead — a separate
    # sign-in browser would collide on the shared profile lock.
    if signin:
        if _reusable_browser() is not None:
            print("\nA reusable browser is already open — sign in there; skipping the separate sign-in step.")
        else:
            _proactive_signin(default_portal, headless)

    # --- Paths ---
    if fetch_paths_ids and _section_needs_browser(fetch_paths_ids, 'paths', default_portal, force):
        print(f"\nProcessing Paths: {fetch_paths_ids}")
        driver = None
        borrowed = False
        try:
            driver, borrowed = _acquire_driver(headless)

            for raw_pid in fetch_paths_ids:
                portal, pid = _resolve_portal(raw_pid, default_portal)
                try:
                    # Skip before navigating when the path and its whole cascade
                    # are already done (backlog #6/#7); --force re-fetches (#8).
                    if not force and path_complete(portal, pid):
                        print(f"•-• [+] Path {_fetch_label(portal, 'paths', pid)} already complete.")
                        continue
                    print(f"Processing Path {_fetch_label(portal, 'paths', pid)} [{portal}]...")
                    p = Path(id=pid, driver=driver, portal=portal)
                    # Load existing to see if we need to fetch?
                    # Fetch command implies scraping/updating.

                    # Fetch data (scrapes remote)
                    p.fetch_data()
                    p.save_json() # Backs up to file and syncs to DB

                    if not no_md:
                        p.save_markdown(toc_only=toc_only)
                        print(f"Path {pid} markdown updated.")
                    print(f"Path {pid} updated.")

                    # Cascade down the tree and fetch every activity in the path.
                    # Partner plans list both courses and standalone labs, so
                    # dispatch by type: courses go through Course.extract_transcript
                    # (which fetches their own labs), labs through the lab helper.
                    # Flags AND the portal are inherited from the path.
                    courses_collection = Courses(portal=portal)
                    courses_collection.load_json()

                    # Partner path fix: activities may be session deep-links whose
                    # trailing id is a video/quiz id, not the catalog id. The
                    # fetch resolves the real id (via the target page's canonical);
                    # capture it so the stored path can be rewritten with correct
                    # ids. Iterate in order and rebuild p.courses.
                    corrected_courses = {}
                    path_changed = False
                    for a_id, activity in list(p.courses.items()):
                        a_name = activity['name']
                        a_type = (activity.get('type') or 'course').lower()
                        a_url = activity.get('url')
                        resolved_id = a_id
                        try:
                            if 'lab' in a_type:
                                print(f"\nPath {pid} > Lab {a_id} - {a_name} [{portal}]")
                                # Partner labs live at a parent-referencing focus URL.
                                lab_obj = _fetch_and_save_lab(a_id, driver, portal, force, no_md, toc_only,
                                                              fetch_url=a_url)
                                if lab_obj is not None:
                                    resolved_id = lab_obj.id
                                    print(f"Lab {resolved_id} updated.")
                            else:
                                print(f"\nPath {pid} > Course {a_id} - {a_name} [{portal}]")
                                c = Course(id=a_id, name=a_name, driver=driver, portal=portal)
                                resolved_id = c.extract_transcript(force=force, no_md=no_md, toc_only=toc_only,
                                                                   no_transcript=no_transcript, fetch_url=a_url) or a_id
                                courses_collection.collection[resolved_id] = a_name
                                print(f"Course {resolved_id} updated.")
                        except Exception as e:
                            print(f"Failed to fetch {a_type} {a_id} in path {pid}: {e}")

                        entry = dict(activity)
                        if resolved_id != a_id:
                            path_changed = True
                            entry['id'] = resolved_id
                            marker = "catalog_lab" if 'lab' in a_type else "course_templates"
                            entry['url'] = f"{p.base_url}/{marker}/{resolved_id}"
                        corrected_courses[resolved_id] = entry

                    # Persist the course names discovered in this path.
                    courses_collection.save_json()

                    # Rewrite the path with corrected ids if any activity resolved.
                    if path_changed:
                        p.courses = corrected_courses
                        p.save_json()
                        if not no_md:
                            p.save_markdown(toc_only=toc_only)
                        print(f"Path {pid} course/lab ids corrected to catalog ids.")

                except Exception as e:
                    print(f"Failed to fetch path {pid}: {e}")
        finally:
            _release_driver(driver, borrowed)
    elif fetch_paths_ids:
        print(f"\nProcessing Paths: {fetch_paths_ids}")
        print("All requested paths are already complete (use --force to re-fetch).")

    # --- Courses ---
    if fetch_courses_ids and _section_needs_browser(fetch_courses_ids, 'courses', default_portal, force):
        print(f"\nProcessing Courses: {fetch_courses_ids}")
        driver = None
        borrowed = False
        try:
             driver, borrowed = _acquire_driver(headless)

             for raw_cid in fetch_courses_ids:
                portal, cid = _resolve_portal(raw_cid, default_portal)
                try:
                    # Skip before navigating when already fully scraped
                    # (backlog #6/#7); --force re-fetches (#8).
                    if not force and course_complete(portal, cid):
                        print(f"•-• [+] Course {_fetch_label(portal, 'courses', cid)} already complete.")
                        continue
                    print(f"Processing Course {_fetch_label(portal, 'courses', cid)} [{portal}]...")
                    c = Course(id=cid, driver=driver, portal=portal)
                    # extract_transcript fetches page, extracts metadata, outline, modules, saves json/md.
                    c.extract_transcript(force=force, no_md=no_md, toc_only=toc_only, no_transcript=no_transcript)
                    print(f"Course {cid} updated.")
                except Exception as e:
                    print(f"Failed to fetch course {cid}: {e}")
        finally:
            _release_driver(driver, borrowed)
    elif fetch_courses_ids:
        print(f"\nProcessing Courses: {fetch_courses_ids}")
        print("All requested courses are already complete (use --force to re-fetch).")

    # --- Labs ---
    if fetch_labs_ids and _section_needs_browser(fetch_labs_ids, 'labs', default_portal, force):
        print(f"\nProcessing Labs: {fetch_labs_ids}")
        driver = None
        borrowed = False
        try:
            driver, borrowed = _acquire_driver(headless)

            for raw_lid in fetch_labs_ids:
                portal, lid = _resolve_portal(raw_lid, default_portal)
                try:
                    print(f"Processing Lab {_fetch_label(portal, 'labs', lid)} [{portal}]...")
                    if _fetch_and_save_lab(lid, driver, portal, force, no_md, toc_only):
                        print(f"Lab {lid} updated.")
                except Exception as e:
                    print(f"Failed to fetch lab {lid}: {e}")
        finally:
            _release_driver(driver, borrowed)
    elif fetch_labs_ids:
        print(f"\nProcessing Labs: {fetch_labs_ids}")
        print("All requested labs are already complete (use --force to re-fetch).")

def cmd_interactive(args):
    """Handle interactive command by launching the interactive menu."""
    import scraper  # lazy import to avoid a circular import
    scraper.interactive_mode()

def cmd_search(args):
    """Handle search command"""
    from services.database import Database
    
    query = args.query
    # Determine type from flags
    search_type = None
    if args.course:
        search_type = 'course'
    elif args.path:
        search_type = 'path'
    elif args.lab:
        search_type = 'lab'
        
    field = args.field
    portal = getattr(args, 'portal', DEFAULT_PORTAL)

    db = Database(portal)

    # Determine tables to search
    tables = []
    
    # Shortcuts for field search if query looks like specific type? No, stick to flags.
    
    if search_type:
        if search_type == 'course':
            tables.append('courses')
        elif search_type == 'path':
            tables.append('paths')
        elif search_type == 'lab':
            tables.append('labs')
    else:
        # Search all
        tables = ['paths', 'courses', 'labs']
    
    if not field:
        print(f"Searching for '{query}' in {tables}...")
    else:
        print(f"Searching for '{query}' in {tables} (field: {field})...")
    
    total_results = 0
    for table in tables:
        results = db.search(table, query, field)
        if results:
            print(f"\n{table} ({len(results)})")
            for res in results:
                # Highlight ID and Name (entities store 'title', lists 'name')
                res_id = res.get('id', 'N/A')
                res_name = res.get('name') or res.get('title') or 'N/A'
                print(f"+|-• \033[35m[{res_id:>5} - {res_name:<72}]\033[0m")
            total_results += len(results)
            
    if total_results == 0:
        print("No results found.")

def cmd_login(args):
    """
    Handle the (hidden) login command.

    Opens a browser at the selected portal's home page so the user can sign in
    manually, then closes it. The webdriver profile persists the session, so
    subsequent fetches for that portal are already authenticated. No scraping
    happens here — it is purely a user-space sign-in step.
    """
    portal = getattr(args, 'portal', DEFAULT_PORTAL)
    url = portal_config(portal)["base"]

    print(f"\n\033[35mLaunching browser to sign in to the '{portal}' portal...\033[0m")
    print(f"Opening: {url}")

    # Login is always visible so the user can interact with the sign-in flow.
    driver = launch_browser(headless=False, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
    try:
        driver.get(url)
        print("Sign in to the portal in the browser window.")
        try:
            input("Press Enter when you are done to close the browser...")
        except (KeyboardInterrupt, EOFError):
            pass
    finally:
        print("Closing browser...")
        driver.quit()

    print(f"Done. Your '{portal}' session is saved to the browser profile.")

def cmd_reindex(args):
    """
    Rebuild the TinyDB ledger (database.json) from the per-item JSON files — the
    single source of truth (backlog #9). Recovers the index after the DB is lost
    and normalizes legacy rows to the compact ledger schema. Never modifies the
    per-item files. Mirrors the Go `reindex` command.
    """
    import glob
    import json
    from services.database import Database

    portal = getattr(args, 'portal', DEFAULT_PORTAL)
    db = Database(portal)
    type_name = {'paths': 'Path', 'courses': 'Course', 'labs': 'Lab'}
    total = 0

    for table_name in ('paths', 'courses', 'labs'):
        kind = type_name[table_name]
        # Existing rows, so catalog-only stubs (ids with no file) survive.
        prior = {str(d.get('id')): d for d in db.all(table_name) if d.get('id') is not None}

        rows = {}
        fetched = 0
        item_dir = os.path.join(str(DATA_FOLDER_NAME), portal, table_name)
        for path in glob.glob(os.path.join(item_dir, '*.json')):
            item_id = os.path.splitext(os.path.basename(path))[0]
            try:
                with open(path, encoding='utf-8') as handle:
                    data = json.load(handle)
            except (ValueError, OSError):
                continue  # skip an unreadable file rather than abort the reindex
            title = data.get('title') or data.get('name') or ''
            rows[item_id] = {
                'id': item_id, 'name': title, 'title': title,
                'type': kind, 'portal': portal,
                'scrapedTime': data.get('scrapedTime'),
            }
            fetched += 1

        # Preserve catalog-only stubs (in the DB, no file), keeping any last-known
        # scrapedTime so a deleted data file doesn't erase the status.
        for item_id, doc in prior.items():
            if item_id in rows:
                continue
            name = doc.get('name') or doc.get('title') or ''
            row = {'id': item_id, 'name': name, 'title': name,
                   'type': kind, 'portal': portal}
            if doc.get('scrapedTime') is not None:
                row['scrapedTime'] = doc.get('scrapedTime')
            rows[item_id] = row

        # Replace the table wholesale, ordered by numeric id when possible.
        def _order_key(i):
            return (0, int(i)) if i.isdigit() else (1, i)

        table = db.db.table(table_name)
        table.truncate()
        if rows:
            table.insert_multiple([rows[i] for i in sorted(rows, key=_order_key)])
        print(f"Reindexed {fetched} {table_name} from files [{portal}]")
        total += fetched

    print(f"Reindex complete: {total} fetched items indexed [{portal}]")

def cmd_browser(args):
    """
    Backlog #14 (cascade of #13): open a persistent, reusable browser.

    Launches a visible Chrome on the selected portal with a fixed remote-
    debugging port, advertises that endpoint (services/browser_endpoint), and
    stays open until Enter / Ctrl+C / SIGTERM. While it is open, `fetch` and
    `list -r` ATTACH to this same window (Selenium debuggerAddress) instead of
    launching their own — so the site never re-challenges for sign-in between
    tasks. On exit it clears the endpoint and closes the browser (it owns it).
    """
    portal = getattr(args, 'portal', DEFAULT_PORTAL)
    profile = args.profile_folder if getattr(args, 'profile_folder', None) else WEBDRIVER_PROFILE_FOLDER_NAME
    url = portal_config(portal)["base"]

    port = browser_endpoint.free_port()
    print(f"\n\033[35mOpening a reusable browser for the '{portal}' portal...\033[0m")
    print(f"Opening: {url}")

    driver = launch_browser(profile_folder=profile, headless=False, browser="chrome", debug_port=port)
    try:
        # Chrome is up and listening on the debug port now; advertise it so
        # fetch/list can reuse this window.
        browser_endpoint.save_endpoint(port)
        driver.get(url)
        print("Browser is open. Sign in and browse freely; fetches will reuse this window.")
        try:
            input("Press Enter to close the browser and exit...")
        except (KeyboardInterrupt, EOFError):
            pass
    finally:
        browser_endpoint.clear_endpoint()
        print("Closing browser...")
        driver.quit()


def cmd_browser_status(args):
    """
    Backlog #14: print whether a reusable browser is advertised and reachable —
    "none" / "alive" / "stale" — mirroring the Go `browser-status` command, so a
    GUI can decide to reuse it or ask the user to close a stale one.
    """
    port, ok = browser_endpoint.load_endpoint()
    if not ok:
        print("none")
    elif browser_endpoint.endpoint_alive(port):
        print("alive")
    else:
        print("stale")

def cmd_mdpath(args):
    """
    Print the vault .md path for a single stored item, or exit non-zero if it
    isn't fetched yet (1) or was fetched without Markdown (2). Mirrors the Go
    `mdpath` command; the GUI uses it to open an item on double-click, and it's
    handy standalone: `open "$(uv run app/main.py mdpath -c 53)"`.
    """
    portal = getattr(args, 'portal', DEFAULT_PORTAL)
    if args.course:
        cls, raw = Course, args.course
    elif args.path:
        cls, raw = Path, args.path
    elif args.lab:
        cls, raw = Lab, args.lab
    else:
        print("mdpath: specify the item with -p, -c, or -l <id>", file=sys.stderr)
        sys.exit(1)

    resolved_portal, ident = _resolve_portal(raw, portal)
    entity = cls(id=ident, portal=resolved_portal)
    entity.load_json()
    if not entity.title:
        print(f"not fetched yet: {cls.__name__.lower()} {ident} [{resolved_portal}]", file=sys.stderr)
        sys.exit(1)
    md = entity._md_path
    if not md.exists():
        print(f"markdown not found (fetched with --no-md?): {md}", file=sys.stderr)
        sys.exit(2)
    print(str(md.resolve()))


def cmd_md(args):
    """Handle md command"""
    toc_only = args.toc
    no_transcript = args.no_transcript
    portal = getattr(args, 'portal', DEFAULT_PORTAL)

    # Check if at least one type is provided
    if not (args.course or args.path or args.lab):
        print("Please specify at least one item type: --course, --path, or --lab.")
        return

    # Process Courses
    if args.course:
        course_ids = [cid.strip() for cid in args.course.split(',') if cid.strip()]
        for cid in course_ids:
            print(f"Generating markdown for Course {cid} [{portal}]...")
            course = Course(id=cid, portal=portal)
            course.load_json()
            if not course.name: # basic check if loaded
                 print(f"Course {cid} data not found. Please fetch/extract first.")
                 continue
            course.save_markdown(toc_only=toc_only, no_transcript=no_transcript)
            print(f"Markdown saved to {course._md_path}")

    # Process Paths
    if args.path:
        path_ids = [pid.strip() for pid in args.path.split(',') if pid.strip()]
        for pid in path_ids:
            print(f"Generating markdown for Path {pid} [{portal}]...")
            path = Path(id=pid, portal=portal)
            path.load_json()
            if not path.name:
                 print(f"Path {pid} data not found. Please fetch first.")
                 continue
            path.save_markdown(toc_only=toc_only)
            print(f"Markdown saved to {path._md_path}")

    # Process Labs
    if args.lab:
        lab_ids = [lid.strip() for lid in args.lab.split(',') if lid.strip()]
        for lid in lab_ids:
            print(f"Generating markdown for Lab {lid} [{portal}]...")
            lab = Lab(id=lid, portal=portal)
            lab.load_json()
             # Lab might not be fully implemented yet, but we support the structure
            if not lab.name:
                 print(f"Lab {lid} data not found.")
                 continue
            lab.save_markdown(toc_only=toc_only)
            print(f"Markdown saved to {lab._md_path}")

def main():
    parser = argparse.ArgumentParser(description="CloudSkillsBoost Scraper CLI")
    # A fixed metavar keeps the visible command list stable and omits the
    # hidden 'login' command from the usage line.
    subparsers = parser.add_subparsers(
        dest='command',
        metavar='{list,l,fetch,f,interactive,i,browser,b,w,md,search,s}',
        help='Command to execute')

    # List command
    parser_l = subparsers.add_parser('list', aliases=['l'], help='List all paths, courses, or labs')
    
    # Mutually exclusive group for type
    group_type = parser_l.add_mutually_exclusive_group()
    group_type.add_argument('--paths', '-p', action='store_true', help='List all paths (default)')
    group_type.add_argument('--courses', '-c', action='store_true', help='List all courses')
    group_type.add_argument('--labs', '-l', action='store_true', help='List all labs')
    
    # Reload flag
    parser_l.add_argument('--reload', '-r', action='store_true', help='Reload list from remote before listing')
    parser_l.add_argument('--headless', action='store_true', help='Run the browser headless (no visible window)')
    add_portal_flags(parser_l)

    # Mutually exclusive group for sorting
    group_sort = parser_l.add_mutually_exclusive_group()
    group_sort.add_argument('--name', '-n', action='store_true', help='Sort by name (default)')
    group_sort.add_argument('--id', '-i', action='store_true', help='Sort by ID')
    
    parser_l.set_defaults(func=cmd_list)

    # Fetch command (Scrape)
    parser_f = subparsers.add_parser('fetch', aliases=['f'], help='Fetch (scrape) courses/paths/labs content')
    parser_f.add_argument('--paths', '-p', nargs='+', metavar='ID', help='Fetch specific path IDs')
    parser_f.add_argument('--courses', '-c', nargs='+', metavar='ID', help='Fetch specific course IDs')
    parser_f.add_argument('--labs', '-l', nargs='+', metavar='ID', help='Fetch specific lab IDs')
    
    # Flags from old course/path commands
    parser_f.add_argument('--force', '-f', action='store_true', help='Force re-extraction even if data exists')
    parser_f.add_argument('--signin', '-s', action='store_true',
                          help='Open the sign-in page and wait before fetching')
    parser_f.add_argument('--no-md', action='store_true', help='Do not generate markdown file')
    parser_f.add_argument('--toc', '-t', action='store_true', help='Table of content only (structure only)')
    # #12: transcripts are always fetched into the JSON; this flag only omits them
    # from the generated Markdown. The old --no-transcript name stays as an alias.
    parser_f.add_argument('--md-no-transcript', '--no-transcript', dest='no_transcript', action='store_true',
                          help='Keep transcripts in the JSON but omit them from the Markdown')
    parser_f.add_argument('--headless', action='store_true', help='Run the browser headless (no visible window)')
    parser_f.add_argument('--log-dir', default=None, metavar='PATH',
                          help='Directory for the per-run activity log (default PROJECT_ROOT/logs, or CSB_LOG_DIR)')
    # Hidden bulk mode: refresh the catalog(s) from the site, then fetch every
    # stored item. Optional KIND: paths (default) / courses / labs / all. Kept
    # out of --help (documented in docs/usage.md) but a real, supported feature.
    parser_f.add_argument('--all', nargs='?', const='paths', metavar='KIND',
                          help=argparse.SUPPRESS)
    add_portal_flags(parser_f)

    parser_f.set_defaults(func=cmd_fetch)

    # Interactive command
    parser_i = subparsers.add_parser('interactive', aliases=['i'], help='Launch the interactive menu')
    parser_i.set_defaults(func=cmd_interactive)

    # Login command (hidden): open the browser at a portal to sign in.
    # Omitting `help` keeps it out of the subcommand help listing.
    parser_login = subparsers.add_parser('login')
    add_portal_flags(parser_login)
    parser_login.set_defaults(func=cmd_login)

    # Browser command: open a reusable browser that later fetches attach to (#14).
    parser_b = subparsers.add_parser('browser', aliases=['b', 'w'],
                                     help='Open a reusable browser you can sign in to; fetches reuse it')
    parser_b.add_argument('--profile-folder', help='Specific webdriver profile folder', default=None)
    add_portal_flags(parser_b)
    parser_b.set_defaults(func=cmd_browser)

    # Browser-status command (hidden, GUI-facing): none / alive / stale (#14).
    parser_bs = subparsers.add_parser('browser-status')
    parser_bs.set_defaults(func=cmd_browser_status)

    # MD command
    parser_m = subparsers.add_parser('md', help='Generate markdown output')
    parser_m.add_argument('--course', '-c', help='List of course IDs (comma-separated)', default=None)
    parser_m.add_argument('--lab', '-l', help='List of lab IDs (comma-separated)', default=None)
    parser_m.add_argument('--path', '-p', help='List of path IDs (comma-separated)', default=None)
    parser_m.add_argument('--toc', '-t', action='store_true', help='Table of content only (structure only)')
    parser_m.add_argument('--md-no-transcript', '--no-transcript', dest='no_transcript', action='store_true',
                          help='Omit transcripts from the generated Markdown')
    add_portal_flags(parser_m)
    parser_m.set_defaults(func=cmd_md)

    # mdpath command: print the vault .md path for one stored item.
    parser_mdpath = subparsers.add_parser('mdpath', help='Print the vault .md path for a stored item')
    parser_mdpath.add_argument('--course', '-c', metavar='ID', help='Course ID or URL', default=None)
    parser_mdpath.add_argument('--path', '-p', metavar='ID', help='Path ID or URL', default=None)
    parser_mdpath.add_argument('--lab', '-l', metavar='ID', help='Lab ID or URL', default=None)
    add_portal_flags(parser_mdpath)
    parser_mdpath.set_defaults(func=cmd_mdpath)

    # Search command
    parser_s = subparsers.add_parser('search', aliases=['s'], help='Search in database')
    parser_s.add_argument('query', help='Search query')
    parser_s.add_argument('--course', '-c', action='store_true', help='Search in courses')
    parser_s.add_argument('--path', '-p', action='store_true', help='Search in paths')
    parser_s.add_argument('--lab', '-l', action='store_true', help='Search in labs')
    parser_s.add_argument('--field', '-f', help='Limit search to specific field', default=None)
    add_portal_flags(parser_s)
    parser_s.set_defaults(func=cmd_search)

    # Reindex command: rebuild database.json from the per-item JSON files (#9).
    parser_reindex = subparsers.add_parser(
        'reindex',
        help='Rebuild the database.json index from the per-item JSON files')
    add_portal_flags(parser_reindex)
    parser_reindex.set_defaults(func=cmd_reindex)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Backlog #1: treat SIGTERM like Ctrl+C for every command, so a wrapping GUI
    # (or `kill`) unwinds through each command's `finally: driver.quit()` and
    # shuts the browser down instead of orphaning it. SIGINT already does this.
    import signal
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    # Migrate any legacy (pre-portal) data into the public scope before running.
    from services.migration import migrate_to_portal_layout
    migrate_to_portal_layout()

    # For a fetch run, timestamp every line and mirror it to a per-run log file
    # (default PROJECT_ROOT/logs, override with --log-dir / CSB_LOG_DIR).
    is_fetch = getattr(args, 'command', None) in ('fetch', 'f')
    if is_fetch:
        from utils import logx
        logx.init(getattr(args, 'log_dir', None))

    # Execute the selected command. A Ctrl+C stops cleanly: each browser is
    # closed by its own finally block during unwinding, and because every item
    # is written atomically as it completes, already-fetched items are kept.
    try:
        args.func(args)
    except KeyboardInterrupt:
        if is_fetch:
            print("\nInterrupted — stopped cleanly; completed items are saved.")
        else:
            print("\nInterrupted.")
        sys.exit(130)
    finally:
        if is_fetch:
            from utils import logx
            logx.close()

if __name__ == "__main__":
    main()
