"""What the Content Credentials say about a document: origin and edit history.

C2PA is about provenance. The signature only makes the record tamper-evident;
the record itself is who made a document, with which tool, from which earlier
version and which components, and what was done at each step. This module

* reads, at recording time, what a package says about itself (the editing
  application in version.xml) and what changed since the previous version
  (package parts and body paragraphs; counts only, never the text), and
* turns a manifest store into a history: one step per recorded version, newest
  first, following the parentOf ingredients.

The editing application and the change summary are statements of whoever
records the version. Hangul does not make them itself (it has no C2PA support),
so they are as reliable as the party named in the signing certificate.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import re
import zipfile
from xml.etree import ElementTree as ET

from .zipbinding import MANIFEST_PATH

CHANGES_LABEL = "io.github.speeno.hwpx_c2pa.changes"
_SECTION = re.compile(r"Contents/section\d+\.xml$")


def editing_application(data: bytes) -> dict | None:
    """Application name and version as written in version.xml by the editor."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            root = ET.fromstring(zf.read("version.xml"))
    except Exception:
        return None
    name = root.get("application")
    if not name:
        return None
    version = (root.get("appVersion") or "").replace(", ", ".").split(" ")[0]
    return {"name": name, "version": version} if version else {"name": name}


def _local(el) -> str:
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()
                if not i.is_dir() and i.filename != MANIFEST_PATH}


def body_paragraphs(parts: dict[str, bytes]) -> list[str]:
    """Text of each paragraph of the body, in document order (table cells included)."""
    out = []
    for name in sorted(n for n in parts if _SECTION.search(n)):
        try:
            root = ET.fromstring(parts[name])
        except ET.ParseError:
            continue
        # Match by local name: the paragraph namespace differs between OWPML editions.
        for p in root.iter():
            if _local(p) != "p":
                continue
            out.append("".join("".join(t.itertext()) for run in p if _local(run) == "run"
                               for t in run if _local(t) == "t"))
    return out


def diff_packages(parent: bytes, current: bytes) -> dict:
    """Summary of what changed between two versions. Holds names and counts, no content."""
    old, new = _parts(parent), _parts(current)
    old_hash = {n: hashlib.sha256(b).digest() for n, b in old.items()}
    new_hash = {n: hashlib.sha256(b).digest() for n, b in new.items()}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    renamed = []
    for a in list(added):  # same bytes under another name (Hangul renames BinData parts)
        match = next((r for r in removed if old_hash[r] == new_hash[a]), None)
        if match:
            renamed.append([match, a])
            added.remove(a)
            removed.remove(match)
    changed = sorted(n for n in set(old) & set(new) if old_hash[n] != new_hash[n])
    before, after = body_paragraphs(old), body_paragraphs(new)
    p_added = p_removed = p_modified = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        if tag != "equal":  # a replaced run counts as modified pairs plus the surplus
            both = min(i2 - i1, j2 - j1)
            p_modified += both
            p_removed += i2 - i1 - both
            p_added += j2 - j1 - both
    return {
        "parts": {"added": added, "removed": removed, "changed": changed, "renamed": renamed,
                  "unchanged": len(set(old) & set(new)) - len(changed)},
        "text": {"paragraphs_before": len(before), "paragraphs_after": len(after),
                 "paragraphs_added": p_added, "paragraphs_removed": p_removed,
                 "paragraphs_modified": p_modified,
                 "characters_before": sum(map(len, before)),
                 "characters_after": sum(map(len, after))},
    }


def describe_changes(changes: dict) -> tuple[str, str]:
    """One line in Korean and one in English."""
    p, t = changes["parts"], changes["text"]
    if not (p["added"] or p["removed"] or p["changed"]):
        return "내용 변경 없음", "no change in content"
    ko, en = [], []
    counts = [(t.get("paragraphs_modified", 0), "수정", "modified"),
              (t["paragraphs_added"], "추가", "added"), (t["paragraphs_removed"], "삭제", "removed")]
    if any(n for n, _, _ in counts):
        ko.append("본문 문단 " + ", ".join(f"{k} {n}" for n, k, _ in counts if n))
        en.append("body paragraphs: " + ", ".join(f"{n} {e}" for n, _, e in counts if n))
    else:
        ko.append("본문 글자 변경 없음")
        en.append("body text unchanged")
    delta = t["characters_after"] - t["characters_before"]
    if delta:
        ko.append(f"글자 수 {t['characters_before']}→{t['characters_after']}")
        en.append(f"characters {t['characters_before']}→{t['characters_after']}")
    for key, k, e in (("changed", "바뀐 파트", "parts changed"), ("added", "추가된 파트", "parts added"),
                      ("removed", "삭제된 파트", "parts removed"), ("renamed", "이름 바뀐 파트", "parts renamed")):
        if p[key]:
            ko.append(f"{k} {len(p[key])}")
            en.append(f"{len(p[key])} {e}")
    return ", ".join(ko), ", ".join(en)


# ---------------------------------------------------------------- reading history
def _step(manifest: dict) -> dict:
    sig = manifest.get("signature_info") or {}
    gen = manifest.get("claim_generator_info") or []
    step = {
        "title": manifest.get("title"),
        "recorded_by": sig.get("common_name"), "issuer": sig.get("issuer"), "time": sig.get("time"),
        "recorder_tool": " ".join(f'{g.get("name", "")} {g.get("version", "")}'.strip() for g in gen),
        "actions": [], "changes": None, "components": [], "parent_problems": [],
    }
    for a in manifest.get("assertions", []):
        label = a.get("label", "")
        if label.startswith("c2pa.actions"):
            for x in a.get("data", {}).get("actions", []):
                agent = x.get("softwareAgent")
                if isinstance(agent, dict):
                    agent = " ".join(str(agent.get(k, "")) for k in ("name", "version")).strip()
                step["actions"].append({
                    "action": x.get("action"), "tool": agent, "description": x.get("description"),
                    "when": x.get("when"),
                    "source_type": (x.get("digitalSourceType") or "").rsplit("/", 1)[-1] or None})
        elif label == CHANGES_LABEL:
            step["changes"] = a.get("data")
    # No time-stamp authority: fall back to the time the recorder stated in the action.
    step["time_source"] = "timestamp" if step["time"] else "claimed"
    if not step["time"]:
        step["time"] = next((a["when"] for a in reversed(step["actions"]) if a.get("when")), None)
    return step


def _problems(ingredient: dict) -> list[str]:
    vr = (ingredient.get("validation_results") or {}).get("activeManifest", {})
    return [x["code"] for x in vr.get("failure", []) if x["code"] != "signingCredential.untrusted"]


def history(store: dict) -> list[dict]:
    """Recorded versions, newest first, by following the parentOf ingredients."""
    manifests = store.get("manifests", {})
    steps, label, seen = [], store.get("active_manifest"), set()
    while label and label in manifests and label not in seen:
        seen.add(label)
        m = manifests[label]
        step = _step(m)
        parent = None
        for ing in m.get("ingredients", []):
            if ing.get("relationship") == "parentOf":
                parent = ing.get("active_manifest")
                step["parent_problems"] = _problems(ing)
                step["parent_title"] = ing.get("title")
            else:
                own = manifests.get(ing.get("active_manifest") or "")
                comp = {"title": ing.get("title"), "relationship": ing.get("relationship"),
                        "has_credentials": own is not None, "problems": _problems(ing)}
                if own:
                    o = _step(own)
                    comp.update(recorded_by=o["recorded_by"], time=o["time"],
                                recorder_tool=o["recorder_tool"], actions=o["actions"])
                step["components"].append(comp)
        steps.append(step)
        label = parent
    for n, step in enumerate(reversed(steps), 1):
        step["version"] = n
    return steps
