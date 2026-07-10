"""
Load optional user preferences from a YAML file that override the built-in
defaults in settings.py, so users don't edit source to relocate their vault,
data, logs, etc. Mirrors the Go internal/config package so both tools honour the
same file.

Precedence for any setting: environment variable > config.yaml > built-in
default (CLI flags, handled by the commands, win over all of these).

Lookup order (first match wins), relative to the project root:
  - $CSB_CONFIG (explicit path)
  - config.yaml
  - config/config.yaml
All keys are optional.
"""

import os
from pathlib import Path

import yaml


def _locate(project_root):
    explicit = os.environ.get("CSB_CONFIG")
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    for candidate in (Path(project_root) / "config.yaml",
                      Path(project_root) / "config" / "config.yaml"):
        if candidate.is_file():
            return candidate
    return None


def load(project_root) -> dict:
    """Return the parsed config as a dict (empty when absent or malformed)."""
    path = _locate(project_root)
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve(env_key: str, config_value, default: str) -> str:
    """Apply precedence: env var (if set) > config value (if set) > default."""
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value
    if config_value:
        return str(config_value)
    return default
