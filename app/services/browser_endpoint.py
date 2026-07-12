"""Backlog #14 (cascade of #13): a persistent "browser" process advertises its
Chrome remote-debugging port here so separate scraper runs (fetch/list) can
attach to the SAME already-signed-in Chrome via Selenium ``debuggerAddress``,
instead of launching their own — which the site would re-challenge for sign-in.

The file is runtime-only: written when the persistent browser starts, removed
when it exits. It shares the exact on-disk contract with the Go core
(``go/internal/browser/endpoint.go``): a ``.csb-browser.json`` next to the shared
profile dir, holding ``{ws, port, pid}``. Either tool can advertise it and the
other can discover it.
"""

import json
import os
import socket
import urllib.request
from pathlib import Path as _Path

from config.settings import WEBDRIVER_PROFILE_FOLDER_NAME


def _endpoint_file() -> str:
    """Path to the endpoint file: ``.csb-browser.json`` next to the profile dir,
    matching the Go core so either tool advertises/discovers the same browser."""
    profile = _Path(str(WEBDRIVER_PROFILE_FOLDER_NAME)).resolve()
    return str(profile.parent / ".csb-browser.json")


def free_port() -> int:
    """Return an available localhost TCP port for Chrome's debug endpoint."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def save_endpoint(port: int) -> None:
    """Advertise the running persistent browser's debug port for reuse."""
    data = {
        "ws": f"ws://127.0.0.1:{port}",
        "port": port,
        "pid": os.getpid(),
    }
    with open(_endpoint_file(), "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def load_endpoint():
    """Return ``(port, True)`` when a persistent browser has advertised one, else
    ``(0, False)``. Python reuses via ``debuggerAddress`` so it reads the port."""
    try:
        with open(_endpoint_file(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return 0, False
    port = data.get("port")
    if not isinstance(port, int) or port <= 0:
        return 0, False
    return port, True


def endpoint_alive(port: int) -> bool:
    """Whether a browser is actually listening on ``port`` — a short HTTP probe of
    ``/json/version`` so a stale endpoint file never causes a hang or a connect
    to nothing."""
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


def clear_endpoint() -> None:
    """Remove the endpoint file when the persistent browser exits."""
    try:
        os.remove(_endpoint_file())
    except OSError:
        pass
