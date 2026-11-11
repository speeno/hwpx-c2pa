"""Fixtures: test certificates, a synthetic HWPX package, a picture with its own credentials.

No Hancom software or third-party sample files are needed. The package below
is a minimal OWPML-shaped ZIP (stored mimetype first, Deflate XML parts, one
picture in BinData); it is not meant to open in a word processor.
"""
from __future__ import annotations

import io
import json
import struct
import zipfile
import zlib

import pytest

from hwpx_c2pa import _lib, devcerts, engine

c2pa = _lib.c2pa
LIBRARY_OK = _lib.library_version() >= _lib.MIN_LIBRARY


def pytest_collection_modifyitems(config, items):
    if not LIBRARY_OK:
        mark = pytest.mark.skip(reason=f"native C2PA library {c2pa.sdk_version()} is too old; "
                                       "run `hwpx-c2pa fetch-lib` first")
        for item in items:
            item.add_marker(mark)

PARTS = {
    "version.xml": '<?xml version="1.0" encoding="UTF-8"?><hv:HCFVersion '
                   'xmlns:hv="http://www.owpml.org/owpml/2024/version" major="5" minor="1"/>',
    "Contents/header.xml": '<?xml version="1.0" encoding="UTF-8"?><hh:head '
                           'xmlns:hh="http://www.owpml.org/owpml/2024/head" secCnt="1"/>',
    "Contents/section0.xml": '<?xml version="1.0" encoding="UTF-8"?><hs:sec '
                             'xmlns:hs="http://www.owpml.org/owpml/2024/section" '
                             'xmlns:hp="http://www.owpml.org/owpml/2024/paragraph">'
                             '<hp:p><hp:run><hp:t>reference text 기준 문장</hp:t></hp:run></hp:p></hs:sec>',
    "settings.xml": '<?xml version="1.0" encoding="UTF-8"?><ha:HWPApplicationSetting '
                    'xmlns:ha="http://www.owpml.org/owpml/2024/app"/>',
    "Contents/content.hpf": '<?xml version="1.0" encoding="UTF-8"?><opf:package '
                            'xmlns:opf="http://www.idpf.org/2007/opf/"><opf:metadata>'
                            '<opf:title>test</opf:title><opf:meta name="creator">tester</opf:meta>'
                            '</opf:metadata><opf:manifest>'
                            '<opf:item id="image1" href="BinData/image1.png" media-type="image/png"/>'
                            '</opf:manifest></opf:package>',
    "META-INF/container.xml": '<?xml version="1.0" encoding="UTF-8"?><ocf:container '
                              'xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">'
                              '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
                              'media-type="application/hwpml-package+xml"/></ocf:rootfiles>'
                              '</ocf:container>',
    "META-INF/manifest.xml": '<?xml version="1.0" encoding="UTF-8"?><odf:manifest '
                             'xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>',
    "Preview/PrvText.txt": "reference text 기준 문장",
}


def tiny_png(w: int = 16, h: int = 16) -> bytes:
    raw = b"".join(b"\x00" + b"".join(bytes((x * 15 % 256, y * 15 % 256, 128)) for x in range(w))
                   for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + \
        chunk(b"IEND", b"")


def build_package(parts: dict[str, bytes | str], picture: bytes | None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, b"application/hwp+zip")
        for name, text in parts.items():
            zf.writestr(name, text.encode() if isinstance(text, str) else text,
                        compress_type=zipfile.ZIP_DEFLATED)
        if picture is not None:
            zf.writestr("BinData/image1.png", picture, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


@pytest.fixture(scope="session")
def certs(tmp_path_factory):
    return devcerts.create(tmp_path_factory.mktemp("certs"))


@pytest.fixture(scope="session")
def signer(certs):
    return engine.load_signer(certs["chain"], certs["key"])


@pytest.fixture(scope="session")
def picture_with_credentials(signer):
    builder = c2pa.Builder(json.dumps({
        "claim_generator_info": [{"name": "hwpx-c2pa-tests", "version": "1"}],
        "assertions": [{"label": "c2pa.actions", "data": {"actions": [
            {"action": "c2pa.created", "digitalSourceType": engine.DIGITAL_CREATION}]}}]}))
    out = io.BytesIO()
    builder.sign(signer, "image/png", io.BytesIO(tiny_png()), out)
    return out.getvalue()


@pytest.fixture(scope="session")
def unsigned_hwpx(picture_with_credentials):
    return build_package(PARTS, picture_with_credentials)


@pytest.fixture(scope="session")
def signed_hwpx(unsigned_hwpx, signer):
    return engine.sign(unsigned_hwpx, signer, title="test.hwpx")
