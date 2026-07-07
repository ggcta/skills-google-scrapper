"""
One-time migration to the per-portal storage layout.

Before multi-portal support, all data lived directly under the data/ and
csbmdvault/ roots and was implicitly the public portal. This moves that legacy
data into a portal-scoped subfolder (data/<portal>/, csbmdvault/<portal>/).

The migration is idempotent and non-destructive: it only moves a legacy item
when the destination does not already exist, and it never touches unrelated
files (e.g. the Obsidian .obsidian config folder in the vault).
"""
import shutil
from pathlib import Path

from config.settings import DATA_FOLDER_NAME, OUTPUT_FOLDER_NAME, DEFAULT_PORTAL, PORTALS

# Entity type folders / collection files that used to sit at the root.
_TYPE_NAMES = ["paths", "courses", "labs"]


def _move_if_absent(src: Path, dest: Path, moved: list):
    """Move src -> dest only when src exists and dest does not."""
    if src.exists() and not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append(str(dest))


def _consolidate_documents(md_root: Path, moved: list):
    """
    Move course document folders into a single shared, portal-agnostic
    csbmdvault/documents/<course_id>/. Course-template ids are global across
    portals, so the same course shares one binary copy instead of duplicating
    it per portal. Handles both the legacy root location and any that ended up
    under a portal folder.
    """
    new_docs = md_root / "documents"
    legacy_locations = [md_root / "courses" / "documents"]
    legacy_locations += [md_root / p / "courses" / "documents" for p in PORTALS]

    for legacy in legacy_locations:
        if legacy.resolve() == new_docs.resolve() or not legacy.is_dir():
            continue
        for doc_id_dir in list(legacy.iterdir()):
            _move_if_absent(doc_id_dir, new_docs / doc_id_dir.name, moved)
        # Remove the now-empty legacy 'documents' (and its 'courses' parent if
        # it, too, is empty). rmdir is a no-op error if not empty — ignore.
        for stale in (legacy, legacy.parent):
            try:
                stale.rmdir()
            except OSError:
                pass


def migrate_to_portal_layout(portal: str = DEFAULT_PORTAL) -> list:
    """
    Relocate legacy root-level data into the given portal scope (default public).
    Returns the list of destinations that were created.
    """
    data_root = Path(DATA_FOLDER_NAME)
    md_root = Path(OUTPUT_FOLDER_NAME)
    moved = []

    # data/database.json -> data/<portal>/database.json
    _move_if_absent(data_root / "database.json", data_root / portal / "database.json", moved)

    # data/<type>/ and data/<type>.json  -> data/<portal>/...
    for name in _TYPE_NAMES:
        _move_if_absent(data_root / name, data_root / portal / name, moved)
        _move_if_absent(data_root / f"{name}.json", data_root / portal / f"{name}.json", moved)

    # csbmdvault/<type>/ and csbmdvault/<type>.md -> csbmdvault/<portal>/...
    for name in _TYPE_NAMES:
        _move_if_absent(md_root / name, md_root / portal / name, moved)
        _move_if_absent(md_root / f"{name}.md", md_root / portal / f"{name}.md", moved)

    # Consolidate course documents into one shared csbmdvault/documents/ folder.
    _consolidate_documents(md_root, moved)

    if moved:
        print(f"\033[36m[migration] Moved legacy data into the '{portal}' portal scope:\033[0m")
        for dest in moved:
            print(f"  -> {dest}")

    return moved
