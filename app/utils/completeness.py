"""
Local completeness checks (backlog #6): decide — WITHOUT touching the browser —
whether an item has already been fully fetched, so cmd_fetch can skip it and
avoid launching the browser (#7) unless --force is given (#8).

The signal is the item's per-item JSON backup existing AND carrying a non-zero
``scrapedTime`` (with a title). This reads the same ``data/<portal>/<type>s/<id>.json``
files the Go core checks (see go/internal/cli/complete.go), which every save
stamps with ``scrapedTime`` — deliberately NOT the TinyDB ``database.json``,
whose older records predate ``scrapedTime`` and would read as incomplete. An item
whose fetch was interrupted before it was saved has no such file/stamp, so it is
correctly seen as incomplete.
"""

import json
import os

from config.settings import DATA_FOLDER_NAME


def _record(portal, kind_plural, id):
    """Load the item's per-item JSON backup, or None if absent/unreadable."""
    path = os.path.join(str(DATA_FOLDER_NAME), portal, kind_plural, f'{id}.json')
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (FileNotFoundError, ValueError, OSError):
        return None


def _record_complete(rec) -> bool:
    """
    True when a loaded record carries a non-zero scrapedTime. scrapedTime is
    stamped only on a successful (atomic) save, so it alone proves a complete
    record exists; a title is not required (some valid records have an empty one).
    """
    if not rec:
        return False
    return (rec.get('scrapedTime') or 0) > 0


def lab_complete(portal, id) -> bool:
    """True when the lab's stored JSON is present and fully scraped."""
    return _record_complete(_record(portal, 'labs', id))


def course_complete(portal, id) -> bool:
    """True when the course's stored JSON is present and fully scraped."""
    return _record_complete(_record(portal, 'courses', id))


def path_complete(portal, id) -> bool:
    """
    Deep check: the path is complete only if its own JSON is fully scraped AND
    every direct child it lists (each course or lab in ``courses``) is itself
    complete. This lets an interrupted cascade (path saved but not all of its
    courses/labs) resume instead of being treated as finished.

    The descent stops one level down — a child course is judged by its own JSON,
    not re-descended into that course's embedded labs — matching the Go core
    (see complete.go), which avoids the activity-id vs lab-id mismatch.
    """
    rec = _record(portal, 'paths', id)
    if not _record_complete(rec):
        return False
    for ref in (rec.get('courses') or {}).values():
        ref_id = ref.get('id')
        if 'lab' in (ref.get('type') or '').lower():
            if not lab_complete(portal, ref_id):
                return False
        elif not course_complete(portal, ref_id):
            return False
    return True


def item_complete(portal, kind, id) -> bool:
    """Dispatch the completeness check by kind (singular or plural)."""
    k = (kind or '').lower()
    if k in ('path', 'paths'):
        return path_complete(portal, id)
    if k in ('course', 'courses'):
        return course_complete(portal, id)
    if k in ('lab', 'labs'):
        return lab_complete(portal, id)
    return False
