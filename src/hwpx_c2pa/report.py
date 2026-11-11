"""Verification window: a self-contained bilingual HTML page for one document.

``hwpx-c2pa view FILE`` writes the page to a temporary file and opens it in the
default browser; ``hwpx-c2pa report FILE -o out.html`` only writes it. The page
has no scripts and loads nothing from the network.
"""
from __future__ import annotations

import datetime as dt
import html
import tempfile
import webbrowser
from pathlib import Path

from . import __version__
from .engine import VerifyResult

STATES = {
    "Trusted": ("ok", "신뢰됨", "Trusted",
                "서명과 내용이 온전하고, 서명자가 신뢰 목록에 있습니다.",
                "Signature and content are intact, and the signer is on the trust list."),
    "Valid": ("warn", "유효", "Valid",
              "서명과 내용은 온전합니다. 서명자는 신뢰 목록에 없습니다.",
              "Signature and content are intact. The signer is not on a trust list."),
    "Invalid": ("bad", "무효", "Invalid",
                "서명 후 문서가 바뀌었거나 서명이 올바르지 않습니다.",
                "The document changed after signing, or the signature is not valid."),
    None: ("none", "자격 증명 없음", "No Content Credentials",
           "이 문서에는 C2PA 콘텐츠 자격 증명이 없습니다.",
           "This document carries no C2PA Content Credentials."),
}
RELATIONS = {"parentOf": "이전 판 / previous version", "componentOf": "구성요소 / component",
             "inputTo": "입력 / input"}
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mute:#5b6675;--line:#dfe3e8;
--ok:#1a7f4b;--okbg:#e6f4ec;--warn:#8a6100;--warnbg:#fdf3d7;--bad:#b3261e;--badbg:#fbe9e7;
--none:#4a5565;--nonebg:#eceff3}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:20px;margin:0 0 2px}h2{font-size:15px;margin:0 0 10px}
.file{color:var(--mute);word-break:break-all;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.badge{display:flex;gap:14px;align-items:center;border-radius:10px;padding:16px 18px}
.badge .mark{font-size:30px;line-height:1;width:44px;height:44px;border-radius:50%;display:grid;
place-items:center;color:#fff;flex:none}
.badge b{font-size:19px}.badge p{margin:2px 0 0}
.ok{background:var(--okbg)}.ok .mark{background:var(--ok)}.ok b{color:var(--ok)}
.warn{background:var(--warnbg)}.warn .mark{background:var(--warn)}.warn b{color:var(--warn)}
.bad{background:var(--badbg)}.bad .mark{background:var(--bad)}.bad b{color:var(--bad)}
.none{background:var(--nonebg)}.none .mark{background:var(--none)}.none b{color:var(--none)}
dl{display:grid;grid-template-columns:minmax(150px,220px) 1fr;gap:6px 14px;margin:0}
dt{color:var(--mute)}dd{margin:0;word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12.5px;font-weight:600}
.t-ok{background:var(--okbg);color:var(--ok)}.t-bad{background:var(--badbg);color:var(--bad)}
.t-none{background:var(--nonebg);color:var(--none)}
ul{margin:0;padding-left:18px}code{font:13px ui-monospace,Menlo,Consolas,monospace}
.scroll{overflow-x:auto}footer{color:var(--mute);font-size:12.5px;margin-top:18px}
@media(max-width:560px){dl{grid-template-columns:1fr}dt{margin-top:6px}}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _row(ko: str, en: str, value) -> str:
    return f"<dt>{ko}<br>{en}</dt><dd>{value}</dd>" if value else ""


def render(result: VerifyResult, filename: str) -> str:
    cls, ko, en, ko_text, en_text = STATES.get(result.state, STATES["Invalid"])
    mark = {"ok": "✓", "warn": "✓", "bad": "✕", "none": "–"}[cls]
    parts = [f'<div class="badge {cls}"><div class="mark">{mark}</div><div><b>{ko} / {en}</b>'
             f"<p>{ko_text}<br>{en_text}</p></div></div>"]
    if result.error:
        parts.append(f'<div class="card"><h2>오류 / Error</h2><code>{_e(result.error)}</code></div>')

    if result.has_manifest:
        actions = ", ".join(f"<code>{_e(a)}</code>" for a in result.actions)
        parts.append('<div class="card"><h2>자격 증명 / Credentials</h2><dl>'
                     + _row("서명자", "Signer", _e(result.signer))
                     + _row("발급자", "Issuer", _e(result.issuer))
                     + _row("서명 시각", "Signed (time-stamp)", _e(result.signed_time))
                     + _row("문서 제목", "Title", _e(result.title))
                     + _row("생성 도구", "Claim generator", _e(result.claim_generator))
                     + _row("동작", "Actions", actions)
                     + _row("저장소의 매니페스트 수", "Manifests in store", result.manifests_in_store)
                     + "</dl></div>")
        bad = [f for f in result.failure if not f.startswith("signingCredential.untrusted")]
        if bad:
            items = "".join(f"<li><code>{_e(f)}</code></li>" for f in bad)
            parts.append(f'<div class="card"><h2>실패 항목 / Failures</h2><ul>{items}</ul></div>')
        if result.ingredients:
            rows = ""
            for i in result.ingredients:
                has = ('<span class="tag t-ok">있음 / yes</span>' if i["has_manifest"]
                       else '<span class="tag t-none">없음 / no</span>')
                fails = [f for f in i["failure"] if f != "signingCredential.untrusted"]
                rows += (f"<tr><td>{_e(i['title'])}</td><td>{_e(RELATIONS.get(i['relationship'], i['relationship']))}"
                         f"</td><td>{has}</td><td>{_e(', '.join(fails)) or '–'}</td></tr>")
            parts.append('<div class="card"><h2>재료(이전 판, 그림) / Ingredients</h2><div class="scroll"><table>'
                         "<tr><th>이름 / Name</th><th>관계 / Relationship</th>"
                         "<th>자체 자격 증명 / Own credentials</th><th>문제 / Problems</th></tr>"
                         f"{rows}</table></div></div>")

    b = result.binding
    if b and "entries" in b:
        rows = ""
        for e in b["entries"]:
            good = e["status"] in ("match", "directory, not listed")
            rows += (f"<tr><td><code>{_e(e['uri'])}</code></td><td class='num'>{e['size']:,}</td>"
                     f"<td><span class='tag {'t-ok' if good else 't-bad'}'>{_e(e['status'])}</span></td></tr>")
        for m in b["missing"]:
            rows += f"<tr><td><code>{_e(m)}</code></td><td></td><td><span class='tag t-bad'>missing</span></td></tr>"
        cd_ok = b["central_directory"] == "match"
        rows += (f"<tr><td>ZIP 중앙 디렉터리 / ZIP central directory</td><td></td>"
                 f"<td><span class='tag {'t-ok' if cd_ok else 't-bad'}'>{b['central_directory']}</span></td></tr>")
        parts.append('<div class="card"><h2>독립 해시 검사 / Independent hash check '
                     f'({_e(b["alg"])}, C2PA 2.5 A.6)</h2><div class="scroll"><table>'
                     "<tr><th>패키지 항목 / Package entry</th><th>바이트 / Bytes</th>"
                     f"<th>결과 / Result</th></tr>{rows}</table></div></div>")

    pkg = result.package or {}
    notes = "".join(f"<li>{_e(n)}</li>" for n in pkg.get("problems", []) + pkg.get("notes", []))
    parts.append('<div class="card"><h2>패키지 / Package</h2><dl>'
                 + _row("OWPML 패키지", "OWPML package", "예 / yes" if pkg.get("is_owpml") else "아니오 / no")
                 + _row("매니페스트 파트", "Manifest part",
                        "<code>META-INF/content_credential.c2pa</code>" if pkg.get("has_manifest_entry")
                        else "없음 / none")
                 + (_row("참고", "Notes", f"<ul>{notes}</ul>") if notes else "") + "</dl></div>")

    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>C2PA 검증 / Verification — {_e(filename)}</title><style>{CSS}</style></head><body><main>"
            f"<h1>C2PA 검증 결과 / Verification result</h1><div class='file'>{_e(filename)}</div>"
            + "".join(parts)
            + f"<footer>hwpx-c2pa {__version__} · 검증 시각 / checked {now}</footer></main></body></html>")


def write(result: VerifyResult, filename: str, output: str | Path | None = None) -> Path:
    if output is None:
        fd = tempfile.NamedTemporaryFile(prefix="hwpx-c2pa-", suffix=".html", delete=False)
        fd.close()
        output = fd.name
    path = Path(output)
    path.write_text(render(result, filename), encoding="utf-8")
    return path


def show(result: VerifyResult, filename: str) -> Path:
    path = write(result, filename)
    webbrowser.open(path.as_uri())
    return path
