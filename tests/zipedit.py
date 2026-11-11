"""Byte-level ZIP edits for tamper tests.

Untouched entries are copied verbatim (local header and data), so a test changes
exactly what it means to change.
"""
from __future__ import annotations

import io
import struct
import zipfile
import zlib

from hwpx_c2pa import zipbinding as zb


def _local(name: str, data: bytes, method: int):
    nb = name.encode("utf-8")
    flags = 0x800 if any(b > 0x7F for b in nb) else 0
    crc = zlib.crc32(data)
    if method == 8:
        co = zlib.compressobj(6, zlib.DEFLATED, -15)
        comp = co.compress(data) + co.flush()
    else:
        comp = data
    lfh = struct.pack("<IHHHHHIIIHH", zb.SIG_LFH, 20, flags, method, 0, 0x21,
                      crc, len(comp), len(data), len(nb), 0) + nb
    return lfh + comp, crc, len(comp), len(data), flags


def rebuild(buf: bytes, *, replace=None, drop=(), add=(), comment=None) -> bytes:
    replace = replace or {}
    z = zb.parse_zip(buf)
    out, cds = bytearray(), []
    for e in z.entries:
        if e.name in drop:
            continue
        cd = bytearray(buf[e.cdh_offset:e.cdh_offset + e.cdh_length])
        if e.name in replace:
            local, crc, csize, usize, flags = _local(e.name, replace[e.name], e.method)
            struct.pack_into("<H", cd, 8, flags)
            struct.pack_into("<III", cd, 16, crc, csize, usize)
        else:
            local = buf[e.lho:e.data_end]
        struct.pack_into("<I", cd, 42, len(out))
        out += local
        cds.append(bytes(cd))
    for name, data in add:
        local, crc, csize, usize, flags = _local(name, data, 8)
        nb = name.encode("utf-8")
        cds.append(struct.pack("<IHHHHHHIIIHHHHHII", zb.SIG_CDH, 0x314, 20, flags, 8, 0, 0x21,
                               crc, csize, usize, len(nb), 0, 0, 0, 0, 0o100644 << 16, len(out)) + nb)
        out += local
    cd_start = len(out)
    for cd in cds:
        out += cd
    cmt = buf[z.eocd_offset + 22:] if comment is None else comment
    out += struct.pack("<IHHHHIIH", zb.SIG_EOCD, 0, 0, len(cds), len(cds),
                       len(out) - cd_start, cd_start, len(cmt)) + cmt
    return bytes(out)


def read_part(buf: bytes, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(buf)) as zf:
        return zf.read(name)


def resave_like_a_word_processor(buf: bytes) -> bytes:
    """Rewrite every entry, drop unknown META-INF parts and rename pictures,
    as Hancom Office HWP 12.30 (macOS) was observed to do on save."""
    src = zipfile.ZipFile(io.BytesIO(buf))
    dst = io.BytesIO()
    with zipfile.ZipFile(dst, "w") as out:
        for info in src.infolist():
            if info.filename in (zb.MANIFEST_PATH, "META-INF/") or info.is_dir():
                continue
            data = src.read(info)
            name = info.filename.replace("BinData/image1.png", "BinData/image2.png")
            method = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            out.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), data,
                         compress_type=method, compresslevel=9 if method else None)
    return dst.getvalue()
