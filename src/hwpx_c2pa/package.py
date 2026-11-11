"""OWPML (KS X 6101) package checks that matter for C2PA embedding."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from .zipbinding import MANIFEST_PATH, parse_zip

OWPML_MIMETYPE = "application/hwp+zip"
DECLARATION_PARTS = ("META-INF/manifest.xml", "Contents/content.hpf")


@dataclass
class PackageReport:
    is_owpml: bool
    has_manifest_entry: bool
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"is_owpml": self.is_owpml, "has_manifest_entry": self.has_manifest_entry,
                "problems": self.problems, "notes": self.notes}


def inspect_package(data: bytes) -> PackageReport:
    z = parse_zip(data)
    first = z.entries[0] if z.entries else None
    mimetype = b""
    if first is not None and first.name == "mimetype" and first.method == 0:
        mimetype = data[first.data_start:first.data_start + first.csize]
    report = PackageReport(is_owpml=mimetype == OWPML_MIMETYPE.encode(),
                           has_manifest_entry=z.find(MANIFEST_PATH) is not None)
    if not report.is_owpml:
        report.problems.append("first entry is not a stored 'mimetype' with application/hwp+zip")
    man = z.find(MANIFEST_PATH)
    if man is not None and (man.method != 0 or man.flags != 0):
        report.problems.append(
            f"{MANIFEST_PATH}: compression method {man.method}, flags {man.flags:#x} "
            "(C2PA A.6 requires stored entry, flags 0)")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        for part in DECLARATION_PARTS:
            if part in names and b"content_credential" in zf.read(part):
                report.notes.append(f"{part} declares the C2PA manifest part")
    dirs = [e.name for e in z.entries if e.is_dir]
    if dirs:
        report.notes.append(f"directory entries: {', '.join(dirs)}")
    return report


def bindata_parts(data: bytes) -> list[tuple[str, bytes]]:
    """Embedded binary parts (pictures and other media) of the package."""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.filename.startswith("BinData/") and not info.is_dir():
                out.append((info.filename, zf.read(info)))
    return out
