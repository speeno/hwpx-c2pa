"""Build the Korean and English sample documents and sign them.

Requires: pip install python-hwpx "hwpx-c2pa[devcerts]"  and  hwpx-c2pa fetch-lib
usage: python make_samples.py [--certs DIR]

Output (per language, in samples/ko and samples/en):
  1-unsigned.hwpx   sample document, no credentials (picture has its own)
  2-signed.hwpx     signed
  4-tampered.hwpx   2-signed with one word changed afterwards (must fail)
3-saved-in-hangul-resigned.hwpx is made by hand: open 2-signed in Hangul, edit,
save, then `hwpx-c2pa sign <file> --parent 2-signed.hwpx`.

The signing certificates are throw-away test certificates. Only the root
certificate (test-root-ca.pem) is kept, so that anyone can validate the samples.
"""
from __future__ import annotations

import argparse
import io
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path

from hwpx.document import HwpxDocument

from hwpx_c2pa import devcerts, engine
from hwpx_c2pa._lib import c2pa

HERE = Path(__file__).resolve().parent

TEXT = {
    "ko": {
        "title": "HWPX 문서의 C2PA 콘텐츠 자격 증명 적용 사례",
        "sections": [
            ("1. 이 문서에 대하여", [
                "이 문서는 hwpx-c2pa 시험용 샘플이다. 문서 패키지 안에 C2PA 콘텐츠 자격 증명이 들어 있다.",
                "자격 증명은 누가 언제 어떤 도구로 문서를 만들었는지를 서명과 함께 기록한다.",
            ]),
            ("2. 확인 방법", [
                "명령: hwpx-c2pa verify 2-signed.hwpx --trust ../test-root-ca.pem",
                "검증 창: hwpx-c2pa view 2-signed.hwpx --trust ../test-root-ca.pem",
            ]),
            ("3. 변조 시험용 문장", [
                "이 문장은 변조 시험의 기준 문장이다. 승인 금액은 1,000,000원이다.",
            ]),
        ],
        "caption": "그림 1 — 자체 C2PA 자격 증명을 가진 그림",
        "table": [["항목", "값"], ["형식", "HWPX (KS X 6101)"], ["규격", "C2PA 2.5 부속서 A.6"]],
        "tamper": ("1,000,000", "9,000,000"),
    },
    "en": {
        "title": "C2PA Content Credentials in an HWPX document: a worked example",
        "sections": [
            ("1. About this document", [
                "This document is a test sample of hwpx-c2pa. The package carries C2PA Content Credentials.",
                "The credentials record, under a signature, who made the document, when, and with which tool.",
            ]),
            ("2. How to check", [
                "Command: hwpx-c2pa verify 2-signed.hwpx --trust ../test-root-ca.pem",
                "Verification window: hwpx-c2pa view 2-signed.hwpx --trust ../test-root-ca.pem",
            ]),
            ("3. Sentence for the tamper test", [
                "This sentence is the reference for the tamper test. The approved amount is 1,000,000 won.",
            ]),
        ],
        "caption": "Figure 1 — A picture that carries its own C2PA credentials",
        "table": [["Item", "Value"], ["Format", "HWPX (KS X 6101)"], ["Specification", "C2PA 2.5, Annex A.6"]],
        "tamper": ("1,000,000", "9,000,000"),
    },
}


def make_png(w: int = 480, h: int = 270) -> bytes:
    """A generated picture (colour gradient with a grid); no third-party content."""
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            grid = (x % 40 == 0) or (y % 40 == 0)
            row += bytes((255, 255, 255) if grid else (40 + x * 180 // w, 90 + y * 120 // h, 200 - x * 120 // w))
        rows.append(bytes(row))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def sign_picture(png: bytes, signer) -> bytes:
    builder = c2pa.Builder(json.dumps({
        "claim_generator_info": [{"name": "hwpx-c2pa-samples", "version": "1"}],
        "title": "figure1.png",
        "assertions": [{"label": "c2pa.actions", "data": {"actions": [
            {"action": "c2pa.created", "digitalSourceType": engine.DIGITAL_CREATION}]}}]}))
    out = io.BytesIO()
    builder.sign(signer, "image/png", io.BytesIO(png), out)
    return out.getvalue()


def build_document(lang: str, picture: bytes) -> bytes:
    t = TEXT[lang]
    doc = HwpxDocument.new()
    doc.add_heading(t["title"], level=1)
    for heading, paragraphs in t["sections"]:
        doc.add_heading(heading, level=2)
        for p in paragraphs:
            doc.add_paragraph(p)
    doc.add_picture(picture, "png", width_mm=80, height_mm=45)
    doc.add_paragraph(t["caption"])
    for row in t["table"]:
        doc.add_paragraph(" : ".join(row))
    return doc.to_bytes()


def tamper(signed: bytes, old: str, new: str) -> bytes:
    """Change one word in the body and write the ZIP again, keeping the manifest entry."""
    src = zipfile.ZipFile(io.BytesIO(signed))
    dst = io.BytesIO()
    with zipfile.ZipFile(dst, "w") as out:
        for info in src.infolist():
            data = src.read(info)
            if info.filename.startswith("Contents/section"):
                assert old.encode() in data
                data = data.replace(old.encode(), new.encode())
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type, zi.external_attr = info.compress_type, info.external_attr
            out.writestr(zi, data)
    return dst.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--certs", help="folder with signer-chain.pem, signer.key, root-ca.pem")
    a = ap.parse_args()
    certs_dir = Path(a.certs) if a.certs else HERE / ".certs"
    if not (certs_dir / "signer.key").exists():
        devcerts.create(certs_dir, common_name="hwpx-c2pa sample signer (TEST)")
    (HERE / "test-root-ca.pem").write_bytes((certs_dir / "root-ca.pem").read_bytes())
    signer = engine.load_signer(certs_dir / "signer-chain.pem", certs_dir / "signer.key")
    picture = sign_picture(make_png(), signer)
    for lang in ("ko", "en"):
        out = HERE / lang
        out.mkdir(exist_ok=True)
        unsigned = build_document(lang, picture)
        signed = engine.sign(unsigned, signer, title=f"sample-{lang}.hwpx")
        (out / "1-unsigned.hwpx").write_bytes(unsigned)
        (out / "2-signed.hwpx").write_bytes(signed)
        (out / "4-tampered.hwpx").write_bytes(tamper(signed, *TEXT[lang]["tamper"]))
        for name in ("1-unsigned", "2-signed", "4-tampered"):
            r = engine.verify((out / f"{name}.hwpx").read_bytes(), trust=HERE / "test-root-ca.pem")
            print(f"{lang}/{name}.hwpx: {r.state or 'no credentials'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
