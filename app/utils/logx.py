"""
Activity logging for the fetch flow.

Mirrors the Go internal/logx package: every printed line is prefixed with a
millisecond-precision timestamp and mirrored to a per-run log file, so a run
leaves an auditable history on disk. It works by wrapping sys.stdout/sys.stderr
with a line-timestamping tee, so existing print() calls need no changes.

The console keeps colour; the file copy is plain (ANSI stripped).
"""

import os
import re
import sys
from datetime import datetime

from config.settings import PROJECT_ROOT

# Millisecond-precision, sortable, ISO-8601-ish (e.g. "2026-07-10 14:23:45.123").
_ANSI = re.compile(r'\x1b\[[0-9;]*m')

_originals = None   # (stdout, stderr) saved at install time
_log_file = None    # open file handle, or None when file logging is unavailable


def _timestamp() -> str:
    # strftime has no millisecond token; take microseconds and trim to 3 digits.
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def dir_default() -> str:
    """The log directory: the CSB_LOG_DIR override, else PROJECT_ROOT/logs."""
    override = os.environ.get('CSB_LOG_DIR')
    return override if override else os.path.join(PROJECT_ROOT, 'logs')


class _Tee:
    """
    A writable stream that prefixes a timestamp to every line it forwards to the
    console, and mirrors an ANSI-stripped copy to the log file. Line state is
    kept across writes so a line split over several write() calls is stamped
    once, at its start.
    """

    def __init__(self, console, log_file):
        self._console = console
        self._log_file = log_file
        self._at_line_start = True

    def write(self, s):
        if not s:
            return 0
        console_parts = []
        file_parts = []
        for ch in s:
            if self._at_line_start and ch != '\n':
                stamp = _timestamp() + ' '
                console_parts.append(stamp)
                file_parts.append(stamp)
                self._at_line_start = False
            console_parts.append(ch)
            file_parts.append(ch)
            if ch == '\n':
                self._at_line_start = True
        self._console.write(''.join(console_parts))
        if self._log_file:
            self._log_file.write(_ANSI.sub('', ''.join(file_parts)))
        return len(s)

    def flush(self):
        self._console.flush()
        if self._log_file:
            self._log_file.flush()

    def isatty(self):
        return getattr(self._console, 'isatty', lambda: False)()


def init(log_dir=None) -> str:
    """
    Open a per-run log file and install the timestamping tee on stdout/stderr.

    Returns the log file path, or '' if the file could not be opened (in which
    case console output is still timestamped — the tee is installed regardless,
    so the timestamps appear even when the log directory is unwritable).
    """
    global _originals, _log_file

    log_dir = log_dir or dir_default()
    path = ''
    log_file = None
    try:
        os.makedirs(log_dir, exist_ok=True)
        name = 'skills-scraper-' + datetime.now().strftime('%Y%m%d-%H%M%S.%f')[:-3] + '.log'
        path = os.path.join(log_dir, name)
        log_file = open(path, 'a', encoding='utf-8', newline='\n')
    except OSError as e:
        print(f"warning: could not open log file in {log_dir}: {e}", file=sys.stderr)
        path = ''

    # Announce the log file on the real console before redirecting, so the meta
    # line stays clean (untimestamped) and out of the file — matching Go.
    if path:
        print(f"Logging this run to {path}")

    _log_file = log_file
    _originals = (sys.stdout, sys.stderr)
    sys.stdout = _Tee(sys.stdout, log_file)
    sys.stderr = _Tee(sys.stderr, log_file)
    return path


def close():
    """Restore stdout/stderr and close the log file (safe if never installed)."""
    global _originals, _log_file
    if _originals is not None:
        sys.stdout, sys.stderr = _originals
        _originals = None
    if _log_file is not None:
        try:
            _log_file.flush()
            _log_file.close()
        finally:
            _log_file = None
