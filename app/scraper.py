#!/usr/bin/env python3
"""
Interactive front-end for the CloudSkillsBoost scraper.

This reuses the command handlers defined in ``main.py`` (``cmd_fetch``,
``cmd_search``, ``cmd_md``, ``cmd_browser``) so an interactive session and a
direct CLI invocation share the exact same logic: fetching a path cascades
down to its courses and their labs, the force flag is inherited down the tree,
markdown/toc/transcript options behave identically, and so on.

Run it directly::

    uv run app/scraper.py

or via the CLI::

    uv run app/main.py interactive
"""
import os
import sys
from types import SimpleNamespace

# Ensure app modules can be imported when run directly (mirrors main.py).
sys.path.append(os.path.join(os.getcwd(), 'app'))

# ANSI helpers
HEADER = "\033[45m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


# MARK: input helpers
def _prompt(message: str) -> str:
    """Prompt the user and return the stripped input."""
    return input(message).strip()


def _prompt_ids(message: str) -> list:
    """
    Prompt for one or more IDs, separated by spaces and/or commas.
    Returns a list of ID strings (empty list if nothing entered).
    """
    raw = _prompt(message)
    if not raw:
        return []
    # Accept both "53 54" and "53,54"
    return [part for part in raw.replace(',', ' ').split() if part]


def _switch_portal(current: str) -> str:
    """
    Select the working portal for the session. Accepts the a/b shorthand
    (a=public, b=partner) or the full portal name. Returns the new portal, or
    the current one if the input is not recognised.
    """
    from config.settings import PORTALS
    keys = list(PORTALS.keys())
    choice = _prompt(
        f"{CYAN}Select working portal:{RESET}\n"
        "  a. public\n"
        "  b. partner\n"
        f"• Select (current: {current}): "
    ).lower()

    mapping = {"a": "public", "public": "public", "b": "partner", "partner": "partner"}
    new_portal = mapping.get(choice)
    if new_portal in keys:
        print(f"{CYAN}Working portal set to: {new_portal}{RESET}")
        return new_portal

    print(f"{YELLOW}Portal unchanged (still {current}).{RESET}")
    return current


def _yes_no(message: str, default: bool = False) -> bool:
    """
    Prompt a yes/no question. Enter accepts the default.
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = _prompt(message + suffix).lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def _prompt_fetch_flags() -> dict:
    """
    Prompt for the flags shared by the fetch command and return them as a dict
    matching the attributes cmd_fetch expects.
    """
    force = _yes_no("Force re-fetch items that already exist?", default=False)

    # Single content-depth choice replaces the previously overlapping
    # "TOC only" and "Skip transcripts" questions.
    depth = _prompt(
        "Content depth? [F]ull (default) / [t]oc only / full but [n]o transcripts: "
    ).lower()
    toc = depth in ("t", "toc")
    no_transcript = depth in ("n", "no", "no-transcript")

    no_md = _yes_no("Skip generating markdown files?", default=False)
    return {
        "force": force,
        "toc": toc,
        "no_transcript": no_transcript,
        "no_md": no_md,
    }


# MARK: menu actions
def _action_fetch(portal: str) -> None:
    """
    Gather a fetch request and delegate to cmd_fetch, which cascades a path
    down to its courses and labs and inherits the flags down the tree.
    Uses the session portal; a full URL among the IDs overrides it per-item.
    """
    import main  # lazy import to avoid a circular import with main.py

    kind = _prompt(
        f"{CYAN}Fetch what?{RESET} [portal: {portal}]\n"
        "  p. A PATH   (→ its courses → their labs)\n"
        "  c. A COURSE (→ its labs)\n"
        "  l. A LAB\n"
        "  b. Back\n"
        "• Select: "
    ).lower()

    if kind == "b" or kind == "":
        return

    if kind not in ("p", "c", "l"):
        print(f"{YELLOW}Please select p, c, l, or b.{RESET}")
        return

    label = {"p": "path", "c": "course", "l": "lab"}[kind]
    ids = _prompt_ids(f"• Enter {label} ID(s) or URL(s) (space/comma separated): ")
    if not ids:
        print(f"{YELLOW}No IDs provided. Cancelled.{RESET}")
        return

    flags = _prompt_fetch_flags()

    # Build the same namespace cmd_fetch receives from argparse.
    # (A full URL among the IDs infers its own portal and overrides this one.)
    args = SimpleNamespace(
        paths=ids if kind == "p" else None,
        courses=ids if kind == "c" else None,
        labs=ids if kind == "l" else None,
        force=flags["force"],
        no_md=flags["no_md"],
        toc=flags["toc"],
        no_transcript=flags["no_transcript"],
        portal=portal,
    )
    main.cmd_fetch(args)


def _action_list(portal: str) -> None:
    """List paths, courses, or labs from the local database (session portal)."""
    from models.paths import Paths
    from models.courses import Courses
    from models.labs import Labs

    kind = _prompt(
        f"{CYAN}List what?{RESET} [portal: {portal}]\n"
        "  p. Paths\n"
        "  c. Courses\n"
        "  l. Labs\n"
        "• Select: "
    ).lower()

    target = {"p": Paths, "c": Courses, "l": Labs}.get(kind)
    if not target:
        print(f"{YELLOW}Please select p, c, or l.{RESET}")
        return

    sort_by = "id" if _yes_no("Sort by ID (instead of name)?", default=False) else "name"

    collection = target(portal=portal)
    collection.load_json()
    if not collection.collection:
        print(f"{YELLOW}Nothing found locally.{RESET}")
        return
    collection.print_list(sort_by=sort_by)


def _action_search(portal: str) -> None:
    """Search the local database (session portal), delegating to cmd_search."""
    import main  # lazy import

    print(f"{CYAN}Search{RESET} [portal: {portal}]")
    query = _prompt("• Search query: ")
    if not query:
        print(f"{YELLOW}Empty query. Cancelled.{RESET}")
        return

    kind = _prompt(
        "• Limit to type? [a]ll / [p]ath / [c]ourse / [l]ab (default all): "
    ).lower()
    field = _prompt("• Limit to a specific field (blank for any): ") or None

    args = SimpleNamespace(
        query=query,
        path=(kind == "p"),
        course=(kind == "c"),
        lab=(kind == "l"),
        field=field,
        portal=portal,
    )
    main.cmd_search(args)


def _action_markdown(portal: str) -> None:
    """(Re)generate markdown from stored data (session portal), via cmd_md."""
    import main  # lazy import

    kind = _prompt(
        f"{CYAN}Generate markdown for?{RESET} [portal: {portal}]\n"
        "  p. Path(s)\n"
        "  c. Course(s)\n"
        "  l. Lab(s)\n"
        "• Select: "
    ).lower()

    if kind not in ("p", "c", "l"):
        print(f"{YELLOW}Please select p, c, or l.{RESET}")
        return

    ids = _prompt_ids("• Enter ID(s) (space/comma separated): ")
    if not ids:
        print(f"{YELLOW}No IDs provided. Cancelled.{RESET}")
        return

    toc = _yes_no("Table of contents only?", default=False)
    no_transcript = False
    if not toc:
        no_transcript = _yes_no("Skip video transcripts?", default=False)

    # cmd_md expects comma-separated strings, not lists.
    joined = ",".join(ids)
    args = SimpleNamespace(
        path=joined if kind == "p" else None,
        course=joined if kind == "c" else None,
        lab=joined if kind == "l" else None,
        toc=toc,
        no_transcript=no_transcript,
        portal=portal,
    )
    main.cmd_md(args)


def _action_browser(portal: str) -> None:
    """Launch a browser for manual login, delegating to cmd_browser.

    Portal is accepted for a uniform action signature; the login page is
    shared across portals so it is not portal-specific here.
    """
    import main  # lazy import
    args = SimpleNamespace(profile_folder=None)
    main.cmd_browser(args)


def _action_login(portal: str) -> None:
    """
    (Hidden) Sign in to the current working portal.

    Opens a browser at the portal's home page so the user can log in; the
    session is saved to the webdriver profile for subsequent fetches.
    Delegates to cmd_login. Not listed in the menu.
    """
    import main  # lazy import
    main.cmd_login(SimpleNamespace(portal=portal))


# MARK: interactive loop
def interactive_mode() -> None:
    """Run the interactive menu loop with a persistent working portal."""
    from config.settings import DEFAULT_PORTAL

    # The session's working portal. All actions operate within it until
    # switched; fetch can still override per-item via a full URL.
    portal = DEFAULT_PORTAL

    actions = {
        "1": _action_fetch,
        "f": _action_fetch,
        "2": _action_list,
        "l": _action_list,
        "3": _action_search,
        "s": _action_search,
        "4": _action_markdown,
        "m": _action_markdown,
        "5": _action_browser,
        "w": _action_browser,
        # Hidden: sign in to the current working portal. Not shown in the menu.
        "login": _action_login,
    }

    while True:
        choice = _prompt(
            "\n"
            f"{CYAN}AVAILABLE OPTIONS{RESET}  (working portal: {CYAN}{portal}{RESET})\n"
            "  1. f: FETCH content (path / course / lab)\n"
            "  2. l: LIST paths / courses / labs\n"
            "  3. s: SEARCH the database\n"
            "  4. m: GENERATE markdown\n"
            "  5. w: LAUNCH browser (manual login)\n"
            "  6. p: SWITCH portal (public / partner)\n"
            "  0. q: QUIT\n"
            "• PLEASE SELECT: "
        ).lower()

        if choice in ("0", "q"):
            print("Good day.")
            return

        if choice in ("6", "p"):
            portal = _switch_portal(portal)
            continue

        action = actions.get(choice)
        if action:
            try:
                action(portal)
            except KeyboardInterrupt:
                print(f"\n{YELLOW}Cancelled.{RESET}")
            except Exception as error:  # keep the menu alive on any failure
                print(f"{RED}Error: {error}{RESET}")
        else:
            print(f"{RED}[INVALID CHOICE] {choice}{RESET}")


if __name__ == "__main__":
    from config.settings import OUTPUT_FOLDER_NAME, DATA_FOLDER_NAME

    # Create the OUTPUT/DATA folders if they do not exist.
    OUTPUT_FOLDER_NAME.mkdir(parents=True, exist_ok=True)
    DATA_FOLDER_NAME.mkdir(parents=True, exist_ok=True)

    # Migrate any legacy (pre-portal) data into the public scope.
    from services.migration import migrate_to_portal_layout
    migrate_to_portal_layout()

    app_title = "CloudSkillsBoost Automation Script"
    print()
    print(f"{HEADER}{app_title:^87}{RESET}")

    try:
        interactive_mode()
    except (KeyboardInterrupt, EOFError):
        print("\nGood day.")

    sys.exit(0)
