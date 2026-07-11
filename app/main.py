#!/usr/bin/env python3
import sys
import os
import argparse
from config.settings import WEBDRIVER_PROFILE_FOLDER_NAME, BASE_URL_PARTNERS, DEFAULT_PORTAL, PORTALS, portal_config

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
from utils.utils import util_portal_and_id


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
        try:
            print("\n\033[35mLaunching browser for list extraction...\033[0m")
            driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)

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
            if driver:
                print("Closing browser...")
                driver.quit()

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
    try:
        print("\n\033[35mLaunching browser to enumerate the catalog...\033[0m")
        driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
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
        if driver:
            print("Closing browser...")
            driver.quit()
    return out

def cmd_fetch(args):
    """Handle fetch (scrape) command"""
    force = args.force
    no_md = args.no_md
    toc_only = args.toc
    no_transcript = args.no_transcript
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

    # --- Paths ---
    if fetch_paths_ids:
        print(f"\nProcessing Paths: {fetch_paths_ids}")
        driver = None
        try:
            print("\n\033[35mLaunching browser for path extraction...\033[0m")
            driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
            
            for raw_pid in fetch_paths_ids:
                portal, pid = _resolve_portal(raw_pid, default_portal)
                try:
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

                    for activity in p.courses.values():
                        a_id = activity['id']
                        a_name = activity['name']
                        a_type = (activity.get('type') or 'course').lower()
                        try:
                            if 'lab' in a_type:
                                print(f"\nPath {pid} > Lab {a_id} - {a_name} [{portal}]")
                                # Partner labs live at a parent-referencing focus URL.
                                if _fetch_and_save_lab(a_id, driver, portal, force, no_md, toc_only,
                                                       fetch_url=activity.get('url')):
                                    print(f"Lab {a_id} updated.")
                            else:
                                print(f"\nPath {pid} > Course {a_id} - {a_name} [{portal}]")
                                courses_collection.collection[a_id] = a_name
                                c = Course(id=a_id, name=a_name, driver=driver, portal=portal)
                                c.extract_transcript(force=force, no_md=no_md, toc_only=toc_only, no_transcript=no_transcript)
                                print(f"Course {a_id} updated.")
                        except Exception as e:
                            print(f"Failed to fetch {a_type} {a_id} in path {pid}: {e}")

                    # Persist the course names discovered in this path.
                    courses_collection.save_json()

                except Exception as e:
                    print(f"Failed to fetch path {pid}: {e}")
        finally:
            if driver:
                print("Closing browser...")
                driver.quit()

    # --- Courses ---
    if fetch_courses_ids:
        print(f"\nProcessing Courses: {fetch_courses_ids}")
        driver = None
        try:
             # Launch browser for authenticated access
             print("\n\033[35mLaunching browser for course extraction...\033[0m")
             driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
             
             for raw_cid in fetch_courses_ids:
                portal, cid = _resolve_portal(raw_cid, default_portal)
                try:
                    print(f"Processing Course {_fetch_label(portal, 'courses', cid)} [{portal}]...")
                    c = Course(id=cid, driver=driver, portal=portal)
                    # extract_transcript fetches page, extracts metadata, outline, modules, saves json/md.
                    c.extract_transcript(force=force, no_md=no_md, toc_only=toc_only, no_transcript=no_transcript)
                    print(f"Course {cid} updated.")
                except Exception as e:
                    print(f"Failed to fetch course {cid}: {e}")
        finally:
            if driver:
                print("Closing browser...")
                driver.quit()

    # --- Labs ---
    if fetch_labs_ids:
        print(f"\nProcessing Labs: {fetch_labs_ids}")
        driver = None
        try:
            print("\n\033[35mLaunching browser for lab extraction...\033[0m")
            driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)

            for raw_lid in fetch_labs_ids:
                portal, lid = _resolve_portal(raw_lid, default_portal)
                try:
                    print(f"Processing Lab {_fetch_label(portal, 'labs', lid)} [{portal}]...")
                    if _fetch_and_save_lab(lid, driver, portal, force, no_md, toc_only):
                        print(f"Lab {lid} updated.")
                except Exception as e:
                    print(f"Failed to fetch lab {lid}: {e}")
        finally:
            if driver:
                print("Closing browser...")
                driver.quit()

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

def cmd_browser(args):
    """Handle browser command"""
    print("\n\033[35mDEBUG: LAUNCHING THE BROWSER...\033[0m\n")
    
    profile = args.profile_folder if args.profile_folder else WEBDRIVER_PROFILE_FOLDER_NAME
    
    driver = launch_browser(profile_folder=profile, headless=False, browser="chrome")
    
    # Open the URL in the default web browser (PARTNERS page usually redirects to login if not logged in)
    driver.get(BASE_URL_PARTNERS)
    print("\n\033[35mDEBUG: BROWSER LAUNCHED.\033[0m")
    print("You can now log in. The script will keep running. Press Ctrl+C to exit and close browser.")
    
    try:
        # Keep the script running so the browser stays open
        # We can also just input() to wait
        input("Press Enter to close the browser and exit...")
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing browser...")
        driver.quit()

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
    parser_f.add_argument('--no-md', action='store_true', help='Do not generate markdown file')
    parser_f.add_argument('--toc', '-t', action='store_true', help='Table of content only (structure only)')
    parser_f.add_argument('--no-transcript', action='store_true', help='Skip video transcripts (courses only)')
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

    # Browser command
    parser_b = subparsers.add_parser('browser', aliases=['b', 'w'], help='Launch browser for manual login')
    parser_b.add_argument('--profile-folder', help='Specific webdriver profile folder', default=None)
    parser_b.set_defaults(func=cmd_browser)

    # MD command
    parser_m = subparsers.add_parser('md', help='Generate markdown output')
    parser_m.add_argument('--course', '-c', help='List of course IDs (comma-separated)', default=None)
    parser_m.add_argument('--lab', '-l', help='List of lab IDs (comma-separated)', default=None)
    parser_m.add_argument('--path', '-p', help='List of path IDs (comma-separated)', default=None)
    parser_m.add_argument('--toc', '-t', action='store_true', help='Table of content only (structure only)')
    parser_m.add_argument('--no-transcript', action='store_true', help='Skip video transcripts (courses only)')
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
