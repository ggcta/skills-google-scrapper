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
    
    # Validation
    if not (fetch_paths_ids or fetch_courses_ids or fetch_labs_ids):
        print("Please specify items to fetch using -p <id>, -c <id>, or -l <id>.")
        return

    # --- Paths ---
    if fetch_paths_ids:
        print(f"\n--- Processing Paths: {fetch_paths_ids} ---")
        driver = None
        try:
            print("\n\033[35mLaunching browser for path extraction...\033[0m")
            driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
            
            for raw_pid in fetch_paths_ids:
                portal, pid = _resolve_portal(raw_pid, default_portal)
                try:
                    print(f"Processing Path {pid} [{portal}]...")
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
                                print(f"\n--- Path {pid} > Lab {a_id} - {a_name} [{portal}] ---")
                                # Partner labs live at a parent-referencing focus URL.
                                if _fetch_and_save_lab(a_id, driver, portal, force, no_md, toc_only,
                                                       fetch_url=activity.get('url')):
                                    print(f"Lab {a_id} updated.")
                            else:
                                print(f"\n--- Path {pid} > Course {a_id} - {a_name} [{portal}] ---")
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
        print(f"\n--- Processing Courses: {fetch_courses_ids} ---")
        driver = None
        try:
             # Launch browser for authenticated access
             print("\n\033[35mLaunching browser for course extraction...\033[0m")
             driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)
             
             for raw_cid in fetch_courses_ids:
                portal, cid = _resolve_portal(raw_cid, default_portal)
                try:
                    print(f"Processing Course {cid} [{portal}]...")
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
        print(f"\n--- Processing Labs: {fetch_labs_ids} ---")
        driver = None
        try:
            print("\n\033[35mLaunching browser for lab extraction...\033[0m")
            driver = launch_browser(headless=headless, browser="chrome", profile_folder=WEBDRIVER_PROFILE_FOLDER_NAME)

            for raw_lid in fetch_labs_ids:
                portal, lid = _resolve_portal(raw_lid, default_portal)
                try:
                    print(f"Processing Lab {lid} [{portal}]...")
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
            print(f"\n--- {table} ({len(results)}) ---")
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

    # Migrate any legacy (pre-portal) data into the public scope before running.
    from services.migration import migrate_to_portal_layout
    migrate_to_portal_layout()

    # Execute the selected command
    args.func(args)

if __name__ == "__main__":
    main()
