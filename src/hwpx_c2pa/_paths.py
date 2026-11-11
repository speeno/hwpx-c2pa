"""File locations shared by the library loader, fetch-lib and the configuration.

This module must not import the C2PA SDK.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "hwpx-c2pa"


def config_path() -> Path:
    if "HWPX_C2PA_CONFIG" in os.environ:
        return Path(os.environ["HWPX_C2PA_CONFIG"])
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "hwpx-c2pa" / "config.json"


def load_config() -> dict:
    """User settings: cert, key, alg, tsa, trust (paths), used when options are omitted."""
    path = config_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def default_library_name() -> str:
    if sys.platform == "win32":
        return "c2pa_c.dll"
    if sys.platform == "darwin":
        return "libc2pa_c.dylib"
    return "libc2pa_c.so"


def versioned_library_name(version: str) -> str:
    stem, ext = os.path.splitext(default_library_name())
    return f"{stem}-{version}{ext}"
