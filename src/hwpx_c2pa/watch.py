"""Re-sign HWPX files in a folder after a word processor saves them.

A save rewrites the package and drops or breaks the C2PA manifest. When a file
changes, stays unchanged for one polling interval, and has no valid binding,
it is signed again with the last signed copy (kept in a cache folder) as the
parentOf ingredient. Files that already carry a valid credential are only
cached, so the watcher never signs its own output twice.
"""
from __future__ import annotations

import time
from pathlib import Path

from .engine import has_valid_binding, sign, write_atomically

SKIP_PREFIXES = (".", "~")
TMP_SUFFIX = ".hwpx-c2pa-tmp"


def _candidates(folder: Path, recursive: bool):
    pattern = "**/*" if recursive else "*"
    for p in folder.glob(pattern):
        if (p.is_file() and p.suffix.lower() == ".hwpx" and not p.name.startswith(SKIP_PREFIXES)
                and ".hwpx-c2pa-cache" not in p.parts):
            yield p


def scan_once(folder: Path, signer, cache: Path, state: dict, *, recursive: bool = False,
              components: bool = True, log=print) -> None:
    for path in _candidates(folder, recursive):
        st = path.stat()
        sig = (st.st_mtime_ns, st.st_size)
        prev = state.get(path)
        if prev == ("done", sig):
            continue
        if prev != ("seen", sig):
            state[path] = ("seen", sig)  # wait until the file stops changing
            continue
        data = path.read_bytes()
        cached = cache / path.relative_to(folder)
        cached.parent.mkdir(parents=True, exist_ok=True)
        if has_valid_binding(data):
            cached.write_bytes(data)
            log(f"valid, cached: {path}")
        else:
            parent = cached.read_bytes() if cached.exists() else None
            try:
                signed = sign(data, signer, title=path.name, parent=parent,
                              parent_title=f"{path.name} (previous)", components=components)
                write_atomically(path, signed)
            except Exception as exc:  # locked, not a ZIP, half-written...
                log(f"could not sign {path}: {exc}")
                state[path] = ("done", sig)
                continue
            cached.write_bytes(signed)
            log(f"signed{' (chained to previous version)' if parent else ''}: {path}")
            st = path.stat()
            sig = (st.st_mtime_ns, st.st_size)
        state[path] = ("done", sig)


def watch(folder: str, signer, *, cache: str | None = None, interval: float = 2.0,
          recursive: bool = False, components: bool = True, once: bool = False, log=print) -> None:
    root = Path(folder).resolve()
    cache_dir = Path(cache) if cache else root / ".hwpx-c2pa-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    state: dict = {}
    if once:  # two passes: the first records sizes, the second acts
        scan_once(root, signer, cache_dir, state, recursive=recursive, components=components, log=log)
        scan_once(root, signer, cache_dir, state, recursive=recursive, components=components, log=log)
        return
    log(f"watching {root} (cache {cache_dir}); Ctrl+C to stop")
    while True:
        scan_once(root, signer, cache_dir, state, recursive=recursive, components=components, log=log)
        time.sleep(interval)
