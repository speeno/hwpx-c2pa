"""Download a native C2PA library that handles Deflate ZIP entries.

The archive comes from the contentauth/c2pa-rs GitHub release and is checked
against the SHA-256 digest published for that release before anything is
extracted. This module must not import the SDK (see _lib.py): the SDK picks
its native library once, at import time.
"""
from __future__ import annotations

import hashlib
import io
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from ._paths import cache_dir, default_library_name, versioned_library_name

RELEASE_TAG = "c2pa-v0.91.11"
RELEASE_VERSION = "0.91.11"
URL = "https://github.com/contentauth/c2pa-rs/releases/download/{tag}/{asset}"

# (sys.platform, machine) -> (asset, sha256) as published on the release page
ASSETS = {
    ("darwin", "arm64"): ("c2pa-v0.91.11-aarch64-apple-darwin.zip",
                          "833b831454daaa5cdad75605bf97dc2e4405e0626bf0c3d5269ae2c9ca3457ae"),
    ("darwin", "x86_64"): ("c2pa-v0.91.11-x86_64-apple-darwin.zip",
                           "c524b746245e83d853e7b291f4e8f266c2340abc9615ee458a580e2102504e65"),
    ("linux", "x86_64"): ("c2pa-v0.91.11-x86_64-unknown-linux-gnu.zip",
                          "de2d5ddbaeacb20002be3ed8ba5ca3232b4010709f0eff46b52f686a5173f4c9"),
    ("linux", "aarch64"): ("c2pa-v0.91.11-aarch64-unknown-linux-gnu.zip",
                           "635c8454df8da07942f7caadda3ccff3fe42ee0f29a8b9a49c81f3daa0a88075"),
    ("win32", "amd64"): ("c2pa-v0.91.11-x86_64-pc-windows-msvc.zip",
                         "21146034348d0c1df52109c3bb6078d81a7e59b00abb09273c32e7beeef7742c"),
    ("win32", "arm64"): ("c2pa-v0.91.11-aarch64-pc-windows-msvc.zip",
                         "24e55b962dbe03ff9bc2212bd10b102b6c74b40fc7a5cb5073650223ada4ab53"),
}


def _machine() -> str:
    m = platform.machine().lower()
    return {"x86_64": "x86_64", "amd64": "amd64", "arm64": "arm64", "aarch64": "aarch64"}.get(m, m)


def asset_for_this_platform() -> tuple[str, str]:
    plat = "linux" if sys.platform.startswith("linux") else sys.platform
    key = (plat, _machine())
    if plat == "win32" and key[1] == "x86_64":
        key = ("win32", "amd64")
    if key not in ASSETS:
        raise RuntimeError(f"no prebuilt C2PA library is known for {key}; build c2pa-rs "
                           f"(c2pa_c_ffi) yourself and set HWPX_C2PA_LIBRARY")
    return ASSETS[key]


def _download(url: str) -> bytes:
    """HTTPS download. Some Python builds (python.org on macOS) ship without CA
    certificates; then certifi is used if installed, else the system curl.
    The SHA-256 check after the download applies in every case."""
    ctx = None
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    try:
        with urllib.request.urlopen(url, timeout=300, context=ctx) as resp:  # noqa: S310
            return resp.read()
    except urllib.error.URLError as exc:
        if not isinstance(getattr(exc, "reason", None), ssl.SSLError) or not shutil.which("curl"):
            raise
    return subprocess.run(["curl", "-fsSL", "--retry", "2", url], check=True,
                          capture_output=True).stdout


def fetch(force: bool = False, log=print) -> Path:
    target = cache_dir() / versioned_library_name(RELEASE_VERSION)
    marker = cache_dir() / "library.txt"
    if target.exists() and not force:
        marker.write_text(target.name, encoding="utf-8")
        log(f"already present: {target}")
        return target
    asset, digest = asset_for_this_platform()
    url = URL.format(tag=RELEASE_TAG, asset=asset)
    log(f"downloading {url}")
    blob = _download(url)
    got = hashlib.sha256(blob).hexdigest()
    if got != digest:
        raise RuntimeError(f"SHA-256 mismatch for {asset}: expected {digest}, got {got}")
    wanted = default_library_name()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        members = [n for n in zf.namelist() if n.rsplit("/", 1)[-1] == wanted]
        if not members:
            raise RuntimeError(f"{wanted} not found in {asset}")
        data = zf.read(members[0])
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        tmp.write(data)
    Path(tmp.name).replace(target)
    marker.write_text(target.name, encoding="utf-8")
    log(f"installed {target} (sha256 of archive verified)")
    return target
