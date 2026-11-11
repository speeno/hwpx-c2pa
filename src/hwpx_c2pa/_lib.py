"""Load the C2PA SDK with a native library that can handle HWPX.

HWPX stores its XML parts with Deflate compression. c2pa-python 0.38.2 and
earlier bundle the native library 0.91.6, which rejects Deflate entries
("compression method not supported: 8"); 0.91.11 handles them. Until
c2pa-python ships a newer library, ``hwpx-c2pa fetch-lib`` downloads one into
the user cache, and this module points c2pa-python at it before the SDK is
imported.

Order of precedence:
  1. ``HWPX_C2PA_LIBRARY``: full path to a ``libc2pa_c`` shared library
  2. the library fetched into the user cache by ``hwpx-c2pa fetch-lib``
  3. the library bundled with c2pa-python
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from ._paths import cache_dir, default_library_name, versioned_library_name

MIN_LIBRARY = (0, 91, 11)
ENV_LIBRARY = "HWPX_C2PA_LIBRARY"


class LibraryTooOld(RuntimeError):
    """The loaded native C2PA library cannot process Deflate-compressed ZIP entries."""


def cached_library() -> Path | None:
    marker = cache_dir() / "library.txt"
    if marker.exists():
        path = cache_dir() / marker.read_text(encoding="utf-8").strip()
        if path.exists():
            return path
    return None


def _point_c2pa_python_at(path: Path) -> Path:
    # c2pa-python looks for C2PA_LIBRARY_NAME in its search path, which ends with
    # the LD_LIBRARY_PATH entries. The file name must differ from the bundled one,
    # otherwise the bundled copy is found first.
    if path.name == default_library_name():
        alias = cache_dir() / "override" / versioned_library_name("custom")
        alias.parent.mkdir(parents=True, exist_ok=True)
        if not alias.exists() or alias.stat().st_size != path.stat().st_size:
            shutil.copyfile(path, alias)
        path = alias
    os.environ["C2PA_LIBRARY_NAME"] = path.name
    paths = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join([str(path.parent)] + ([paths] if paths else []))
    return path


def _configure() -> Path | None:
    if "c2pa" in sys.modules:
        return None  # already imported elsewhere; too late to redirect
    override = os.environ.get(ENV_LIBRARY)
    path = Path(override) if override else cached_library()
    if path is not None and path.exists():
        return _point_c2pa_python_at(path)
    return None


LIBRARY_OVERRIDE = _configure()

import c2pa  # noqa: E402  (must follow _configure)


def library_version() -> tuple[int, ...]:
    raw = c2pa.sdk_version()
    return tuple(int(p) for p in raw.split("-")[0].split(".")[:3])


def ensure_supported() -> None:
    if library_version() < MIN_LIBRARY:
        need = ".".join(map(str, MIN_LIBRARY))
        raise LibraryTooOld(
            f"native C2PA library {c2pa.sdk_version()} cannot read Deflate-compressed "
            f"ZIP entries, which every HWPX file uses; version {need} or later is "
            f"needed. Run `hwpx-c2pa fetch-lib`, or set {ENV_LIBRARY} to a newer library.")
