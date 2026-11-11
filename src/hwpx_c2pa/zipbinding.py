"""Independent computation of the C2PA hard binding for ZIP-based assets.

C2PA Technical Specification 2.5, Annex A.6:
  * each entry except the manifest store is hashed over its local file header,
    its compressed (or encrypted) data and its data descriptor, if any;
  * the central directory headers and the end-of-central-directory record are
    hashed together, skipping the CRC-32 field of the manifest entry's header;
  * the manifest store is the stored entry META-INF/content_credential.c2pa.

This module needs no C2PA SDK. It is used to cross-check what the SDK wrote.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

MANIFEST_PATH = "META-INF/content_credential.c2pa"

SIG_LFH = 0x04034B50
SIG_CDH = 0x02014B50
SIG_EOCD = 0x06054B50
SIG_DD = 0x08074B50
_HASHES = {"sha256": hashlib.sha256, "sha384": hashlib.sha384, "sha512": hashlib.sha512}


@dataclass
class Entry:
    name: str
    flags: int
    method: int
    crc: int
    csize: int
    usize: int
    lho: int          # offset of the local file header
    cdh_offset: int   # offset of this entry's central directory header
    cdh_length: int
    data_start: int = 0
    data_end: int = 0  # end of the compressed data, plus the data descriptor if any

    @property
    def is_dir(self) -> bool:
        return self.name.endswith("/")


@dataclass
class ZipLayout:
    entries: list[Entry]
    cd_offset: int
    cd_size: int
    eocd_offset: int
    length: int

    def find(self, name: str) -> Entry | None:
        return next((e for e in self.entries if e.name == name), None)


def parse_zip(buf: bytes) -> ZipLayout:
    """Parse the central directory and locate each entry's local block."""
    tail = buf[-(0xFFFF + 22):]
    pos = tail.rfind(struct.pack("<I", SIG_EOCD))
    if pos < 0:
        raise ValueError("not a ZIP file: end of central directory record not found")
    eocd = len(buf) - len(tail) + pos
    (_, _, _, _, total, cd_size, cd_offset, _) = struct.unpack_from("<IHHHHIIH", buf, eocd)
    if 0xFFFFFFFF in (cd_size, cd_offset) or total == 0xFFFF:
        raise ValueError("ZIP64 archives are not supported")

    entries = []
    p = cd_offset
    for _ in range(total):
        (sig, _vm, _vn, flags, method, _t, _d, crc, csize, usize,
         nlen, elen, clen, _disk, _ia, _ea, lho) = struct.unpack_from("<IHHHHHHIIIHHHHHII", buf, p)
        if sig != SIG_CDH:
            raise ValueError(f"bad central directory header at offset {p}")
        raw = buf[p + 46:p + 46 + nlen]
        name = raw.decode("utf-8" if flags & 0x800 else "cp437")
        length = 46 + nlen + elen + clen
        entries.append(Entry(name, flags, method, crc, csize, usize, lho, p, length))
        p += length

    for e in entries:
        if struct.unpack_from("<I", buf, e.lho)[0] != SIG_LFH:
            raise ValueError(f"bad local file header for {e.name}")
        nlen, elen = struct.unpack_from("<HH", buf, e.lho + 26)
        e.data_start = e.lho + 30 + nlen + elen
        end = e.data_start + e.csize
        if e.flags & 0x8:  # a data descriptor follows the data
            if end + 4 <= len(buf) and struct.unpack_from("<I", buf, end)[0] == SIG_DD:
                end += 4
            end += 12
        e.data_end = end
    return ZipLayout(entries, cd_offset, cd_size, eocd, len(buf))


def entry_digest(buf: bytes, e: Entry, alg: str = "sha256") -> tuple[bytes, int]:
    block = buf[e.lho:e.data_end]
    return _HASHES[alg](block).digest(), len(block)


def central_directory_digest(buf: bytes, z: ZipLayout, alg: str = "sha256") -> bytes:
    h = _HASHES[alg]()
    man = z.find(MANIFEST_PATH)
    if man is None:
        h.update(buf[z.cd_offset:])
    else:
        crc_at = man.cdh_offset + 16
        h.update(buf[z.cd_offset:crc_at])
        h.update(buf[crc_at + 4:])
    return h.digest()


@dataclass
class BindingReport:
    alg: str
    entries: list[tuple[str, int, str]] = field(default_factory=list)  # (name, size, status)
    missing: list[str] = field(default_factory=list)
    central_directory_match: bool = False

    @property
    def ok(self) -> bool:
        return (self.central_directory_match and not self.missing
                and all(s in ("match", DIR_UNLISTED) for _, _, s in self.entries))

    def to_dict(self) -> dict:
        return {"alg": self.alg, "ok": self.ok,
                "central_directory": "match" if self.central_directory_match else "mismatch",
                "entries": [{"uri": n, "size": s, "status": st} for n, s, st in self.entries],
                "missing": self.missing}


DIR_UNLISTED = "directory, not listed"


def compare(buf: bytes, recorded: dict[str, tuple[bytes, int | None]], recorded_cd: bytes,
            alg: str = "sha256") -> BindingReport:
    """Recompute the binding and compare it with the values recorded in a manifest.

    C2PA 2.5 A.6.2.1 hashes every entry, directory entries included; the SDK
    records a directory under its name without the trailing slash. A directory
    entry that the signer added while embedding the manifest is not listed and is
    protected by the central directory hash only; it is reported, not failed.
    """
    z = parse_zip(buf)
    report = BindingReport(alg)
    matched = set()
    for e in z.entries:
        if e.name == MANIFEST_PATH:
            continue
        digest, size = entry_digest(buf, e, alg)
        key = e.name if e.name in recorded else (
            e.name.rstrip("/") if e.is_dir and e.name.rstrip("/") in recorded else None)
        if key is None:
            status = DIR_UNLISTED if e.is_dir else "not in manifest"
        else:
            matched.add(key)
            rec = recorded[key]
            status = "match" if rec[0] == digest and rec[1] in (None, size) else "mismatch"
        report.entries.append((e.name, size, status))
    report.missing = sorted(set(recorded) - matched)
    report.central_directory_match = recorded_cd == central_directory_digest(buf, z, alg)
    return report
