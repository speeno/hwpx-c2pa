"""Provenance window: a self-contained bilingual HTML page for one document.

The page answers, in this order: where the document comes from, what was done
to it version by version, which components it contains and where they come
from, and last whether that record can be relied on (signature, hashes).

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
    "Trusted": ("ok", "출처 기록 확인됨 (신뢰됨)", "Provenance confirmed (Trusted)",
                "아래 출처와 이력은 기록된 뒤 바뀌지 않았고, 기록자가 신뢰 목록에 있습니다.",
                "The provenance and history below are unchanged since they were recorded, "
                "and the recording party is on the trust list."),
    "Valid": ("warn", "출처 기록 온전함 (유효)", "Provenance record intact (Valid)",
              "아래 출처와 이력은 기록된 뒤 바뀌지 않았습니다. 기록자는 신뢰 목록에 없습니다.",
              "The provenance and history below are unchanged since they were recorded. "
              "The recording party is not on a trust list."),
    "Invalid": ("bad", "출처 기록과 문서가 맞지 않음 (무효)", "Document does not match its record (Invalid)",
                "마지막 기록 이후 문서가 바뀌었거나 기록이 손상되었습니다. 아래 이력은 지금 문서를 설명하지 못합니다.",
                "The document changed after the last record, or the record is damaged. "
                "The history below does not describe the document as it is now."),
    None: ("none", "출처 기록 없음", "No provenance record",
           "이 문서에는 C2PA 콘텐츠 자격 증명이 없어 출처와 수정 이력을 확인할 수 없습니다.",
           "This document carries no C2PA Content Credentials; its origin and history cannot be checked."),
}
ACTIONS = {"c2pa.created": ("만듦", "Created"), "c2pa.opened": ("이전 판을 엶", "Opened the previous version"),
           "c2pa.edited": ("편집함", "Edited"), "c2pa.placed": ("넣음", "Placed"),
           "c2pa.converted": ("형식 변환", "Converted"), "c2pa.published": ("배포함", "Published"),
           "c2pa.repackaged": ("다시 묶음", "Repackaged")}
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
.tl{list-style:none;margin:0;padding:0}.tl>li{position:relative;padding:0 0 18px 30px;border-left:2px solid var(--line);margin-left:9px}
.tl>li:last-child{border-left-color:transparent;padding-bottom:0}
.tl>li::before{content:"";position:absolute;left:-8px;top:3px;width:14px;height:14px;border-radius:50%;background:var(--ok);border:2px solid var(--card)}
.tl.stale>li::before{background:var(--none)}
.tl h3{font-size:14.5px;margin:0 0 4px}.tl .meta{color:var(--mute);font-size:13.5px}
.tl .act{margin:6px 0 0;padding:0;list-style:none}.tl .act li{margin:3px 0}
.chg{margin-top:6px;font-size:13.5px;background:var(--bg);border-radius:8px;padding:8px 10px}
.small{color:var(--mute);font-size:13px}details summary{cursor:pointer;font-weight:600}
@media(max-width:560px){dl{grid-template-columns:1fr}dt{margin-top:6px}}
"""


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _row(ko: str, en: str, value) -> str:
    return f"<dt>{ko}<br>{en}</dt><dd>{value}</dd>" if value else ""


def _time(step: dict) -> str:
    if not step.get("time"):
        return "–"
    kind = ("타임스탬프 / time-stamp" if step.get("time_source") == "timestamp"
            else "기록자가 밝힌 시각 / stated by the recorder")
    return f"{_e(step['time'])} <span class='small'>({kind})</span>"


def _who(step: dict) -> str:
    who = _e(step.get("recorded_by") or "–")
    return who + (f" <span class='small'>({_e(step['issuer'])})</span>" if step.get("issuer") else "")


def _actions(actions: list[dict]) -> str:
    items = ""
    for a in actions:
        ko, en = ACTIONS.get(a["action"], (a["action"], a["action"]))
        line = f"<b>{_e(ko)} / {_e(en)}</b> <code>{_e(a['action'])}</code>"
        if a.get("tool"):
            line += f" · 편집 프로그램 / editor: {_e(a['tool'])}"
        if a.get("description"):
            line += f"<br><span class='small'>{_e(a['description'])}</span>"
        items += f"<li>{line}</li>"
    return f"<ul class='act'>{items}</ul>" if items else ""


def _changes(ch: dict | None) -> str:
    if not ch:
        return ""
    p, t = ch["parts"], ch["text"]
    rows = [f"본문 문단 / body paragraphs: {t['paragraphs_before']} → {t['paragraphs_after']} "
            f"(수정 / modified {t.get('paragraphs_modified', 0)}, 추가 / added {t['paragraphs_added']}, "
            f"삭제 / removed {t['paragraphs_removed']})",
            f"글자 수 / characters: {t['characters_before']:,} → {t['characters_after']:,}"]
    for key, label in (("changed", "바뀐 파트 / parts changed"), ("added", "추가된 파트 / parts added"),
                       ("removed", "삭제된 파트 / parts removed")):
        if p[key]:
            rows.append(f"{label}: " + ", ".join(f"<code>{_e(n)}</code>" for n in p[key]))
    if p["renamed"]:
        rows.append("이름만 바뀐 파트 / parts renamed, same bytes: "
                    + ", ".join(f"<code>{_e(a)}</code> → <code>{_e(b)}</code>" for a, b in p["renamed"]))
    return ("<div class='chg'><b>이전 판과의 차이 / Changes since the previous version</b><br>"
            + "<br>".join(rows) + "</div>")


def _components(components: list[dict]) -> str:
    out = ""
    for c in components:
        if c["has_credentials"]:
            acts = ", ".join(a["action"] for a in c.get("actions", []))
            own = (f"<span class='tag t-ok'>자체 출처 기록 있음 / has its own credentials</span> "
                   f"{_e(c.get('recorded_by') or '–')}, {_e(c.get('recorder_tool') or '–')}"
                   + (f", <code>{_e(acts)}</code>" if acts else ""))
        else:
            own = "<span class='tag t-none'>출처 기록 없음 / no credentials</span>"
        bad = (f" <span class='tag t-bad'>{_e(', '.join(c['problems']))}</span>" if c["problems"] else "")
        out += f"<li><code>{_e(c['title'])}</code> — {own}{bad}</li>"
    return (f"<div class='chg'><b>문서 안 구성요소의 출처 / Provenance of components in the document</b>"
            f"<ul>{out}</ul></div>") if out else ""


def render(result: VerifyResult, filename: str) -> str:
    cls, ko, en, ko_text, en_text = STATES.get(result.state, STATES["Invalid"])
    mark = {"ok": "✓", "warn": "✓", "bad": "✕", "none": "–"}[cls]
    parts = [f'<div class="badge {cls}"><div class="mark">{mark}</div><div><b>{ko} / {en}</b>'
             f"<p>{ko_text}<br>{en_text}</p></div></div>"]
    if result.error:
        parts.append(f'<div class="card"><h2>오류 / Error</h2><code>{_e(result.error)}</code></div>')

    steps = result.history
    if steps:
        first, last = steps[-1], steps[0]
        origin_tool = next((a["tool"] for a in first["actions"] if a.get("tool")), None)
        parts.append('<div class="card"><h2>출처 / Provenance</h2><dl>'
                     + _row("처음 기록한 주체", "First recorded by", _who(first))
                     + _row("처음 기록한 때", "First recorded", _time(first))
                     + _row("만든 프로그램", "Made with", _e(origin_tool))
                     + _row("기록된 판 수", "Recorded versions", len(steps))
                     + (_row("현재 판을 기록한 주체", "Current version recorded by", _who(last))
                        + _row("현재 판을 기록한 때", "Current version recorded", _time(last))
                        if len(steps) > 1 else "")
                     + _row("기록 도구", "Recording tool", _e(last.get("recorder_tool")))
                     + "</dl></div>")
        items = ""
        for step in steps:
            current = " · 현재 판 / current" if step is last else ""
            broken = (f"<div><span class='tag t-bad'>이전 판 기록 문제 / problem in the earlier record: "
                      f"{_e(', '.join(step['parent_problems']))}</span></div>"
                      if step["parent_problems"] else "")
            items += (f"<li><h3>판 / Version {step['version']}{current} — {_e(step.get('title'))}</h3>"
                      f"<div class='meta'>{_time(step)} · 기록 / recorded by {_who(step)}</div>"
                      f"{_actions(step['actions'])}{_changes(step.get('changes'))}"
                      f"{_components(step['components'])}{broken}</li>")
        parts.append('<div class="card"><h2>수정 이력 / Edit history '
                     '<span class="small">(최신 판부터 / newest first)</span></h2>'
                     f'<ol class="tl{"" if result.integrity_ok else " stale"}">{items}</ol>'
                     '<p class="small">편집 프로그램과 변경 요약은 판을 기록한 주체가 밝힌 내용입니다. '
                     '변경 요약에는 개수와 파트 이름만 들어가며 본문은 들어가지 않습니다.<br>'
                     'The editor and the change summary are statements of the party that recorded the '
                     'version. The summary holds counts and part names only, never the text.</p></div>')

    if result.has_manifest:
        bad = [f for f in result.failure if not f.startswith("signingCredential.untrusted")]
        if bad:
            items = "".join(f"<li><code>{_e(f)}</code></li>" for f in bad)
            parts.append(f'<div class="card"><h2>맞지 않는 항목 / What does not match</h2><ul>{items}</ul></div>')

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
        verdict = ("<span class='tag t-ok'>모두 일치 / all match</span>" if b["ok"]
                   else "<span class='tag t-bad'>불일치 / mismatch</span>")
        parts.append(f'<div class="card"><details{"" if b["ok"] else " open"}><summary>이 기록을 믿을 수 있는 근거: '
                     f'문서와 기록의 결속 / Why the record can be relied on: binding to the document {verdict}'
                     '</summary><p class="small">기록에는 패키지의 모든 항목과 ZIP 중앙 디렉터리의 해시가 들어 있고, '
                     '기록 전체에 기록자의 서명이 붙어 있습니다. 아래는 해시를 SDK와 별개로 다시 계산한 결과입니다.<br>'
                     'The record holds a hash of every package entry and of the ZIP central directory, and the '
                     'whole record is signed by the recording party. Below, the hashes are recomputed '
                     f'independently of the SDK ({_e(b["alg"])}, C2PA 2.5 A.6).</p><div class="scroll"><table>'
                     "<tr><th>패키지 항목 / Package entry</th><th>바이트 / Bytes</th>"
                     f"<th>결과 / Result</th></tr>{rows}</table></div></details></div>")

    pkg = result.package or {}
    notes = "".join(f"<li>{_e(n)}</li>" for n in pkg.get("problems", []) + pkg.get("notes", []))
    parts.append('<div class="card"><h2>패키지 / Package</h2><dl>'
                 + _row("OWPML 패키지", "OWPML package", "예 / yes" if pkg.get("is_owpml") else "아니오 / no")
                 + _row("출처 기록 파트", "Credentials part",
                        "<code>META-INF/content_credential.c2pa</code>" if pkg.get("has_manifest_entry")
                        else "없음 / none")
                 + _row("저장소의 매니페스트 수", "Manifests in store", result.manifests_in_store)
                 + (_row("참고", "Notes", f"<ul>{notes}</ul>") if notes else "") + "</dl></div>")

    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>C2PA 출처 확인 / Provenance — {_e(filename)}</title><style>{CSS}</style></head><body><main>"
            f"<h1>문서 출처와 수정 이력 / Document provenance and history</h1><div class='file'>{_e(filename)}</div>"
            + "".join(parts)
            + f"<footer>hwpx-c2pa {__version__} · 확인 시각 / checked {now}</footer></main></body></html>")


def write(result: VerifyResult, filename: str, output: str | Path | None = None) -> Path:
    if output is None:
        fd = tempfile.NamedTemporaryFile(prefix="hwpx-c2pa-", suffix=".html", delete=False)
        fd.close()
        output = fd.name
    path = Path(output)
    path.write_text(render(result, filename), encoding="utf-8")
    return path


def _edge() -> str | None:
    """Microsoft Edge on Windows, used to show the page as a window of its own."""
    import os
    for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.environ.get("LOCALAPPDATA")):
        if root:
            exe = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if exe.exists():
                return str(exe)
    return None


def show(result: VerifyResult, filename: str, app: bool = False) -> Path:
    """Open the page: in the default browser, or with app=True as a separate window
    without browser controls (Windows with Edge; elsewhere the browser is used)."""
    import subprocess
    import sys
    path = write(result, filename)
    edge = _edge() if app and sys.platform == "win32" else None
    if edge:
        subprocess.Popen([edge, f"--app={path.as_uri()}", "--window-size=940,1000"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True,
                         creationflags=0x00000008 | 0x00000200)  # detached, own process group
    else:
        webbrowser.open(path.as_uri())
    return path
