"""Sign and verify C2PA Content Credentials in HWPX (OWPML) packages.

The manifest store is embedded as described in C2PA 2.5 Annex A.6. The C2PA SDK
does not list the OWPML media type, so packages are handed to it under the
generic ZIP format; file names and extensions do not matter.

Word processors rewrite the whole package on save, which removes or breaks the
manifest. Each saved version is therefore signed again with a new manifest
whose parentOf ingredient is the previous signed version (ZIP assets cannot
carry C2PA update manifests).
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from ._lib import c2pa, ensure_supported
from .package import OWPML_MIMETYPE, bindata_parts, inspect_package
from .provenance import (CHANGES_LABEL, describe_changes, diff_packages, editing_application,
                         history)
from .zipbinding import compare

ZIP_FORMAT = "zip"
PARENT_LABEL = "previous-version"
COMPONENT_FORMATS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                     "gif": "image/gif", "tif": "image/tiff", "tiff": "image/tiff",
                     "webp": "image/webp", "svg": "image/svg+xml", "mp4": "video/mp4",
                     "mp3": "audio/mpeg", "wav": "audio/wav", "pdf": "application/pdf"}
DIGITAL_CREATION = "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCreation"


class NoManifest(Exception):
    """The package carries no C2PA manifest store."""


# ------------------------------------------------------------------ signer, trust
def load_signer(cert: str | os.PathLike, key: str | os.PathLike, alg: str = "es256",
                tsa: str | None = None) -> c2pa.Signer:
    """Signer from a PEM certificate chain (leaf first, no root) and a PEM private key."""
    cert_pem = Path(cert).read_bytes()
    key_pem = Path(key).read_bytes()
    return c2pa.Signer.from_info(c2pa.C2paSignerInfo(alg=alg, sign_cert=cert_pem,
                                                     private_key=key_pem, ta_url=tsa))


def _reader(data: bytes, trust: str | os.PathLike | None = None) -> c2pa.Reader:
    try:
        if trust:
            anchors = Path(trust).read_text(encoding="ascii")
            settings = c2pa.Settings.from_json(json.dumps(
                {"verify": {"verify_trust": True}, "trust": {"trust_anchors": anchors}}))
            return c2pa.Reader(ZIP_FORMAT, io.BytesIO(data), context=c2pa.Context(settings=settings))
        return c2pa.Reader(ZIP_FORMAT, io.BytesIO(data))
    except Exception as exc:
        if "ManifestNotFound" in type(exc).__name__ or "no JUMBF" in str(exc):
            raise NoManifest(str(exc)) from exc
        raise


# ----------------------------------------------------------------------- verify
STATE_KO = {"Trusted": "신뢰됨", "Valid": "유효", "Invalid": "무효", None: "자격 증명 없음"}


@dataclass
class VerifyResult:
    state: str | None = None
    title: str | None = None
    claim_generator: str | None = None
    signer: str | None = None
    issuer: str | None = None
    signed_time: str | None = None
    actions: list[str] = field(default_factory=list)
    success: list[str] = field(default_factory=list)
    informational: list[str] = field(default_factory=list)
    failure: list[str] = field(default_factory=list)
    ingredients: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)  # recorded versions, newest first
    manifests_in_store: int = 0
    binding: dict | None = None
    package: dict | None = None
    error: str | None = None

    @property
    def has_manifest(self) -> bool:
        return self.state is not None

    @property
    def integrity_ok(self) -> bool:
        """Signature and hard binding intact (trust in the signer is a separate question)."""
        bad = [f for f in self.failure if not f.startswith("signingCredential.untrusted")]
        return self.has_manifest and not bad and (self.binding is None or self.binding["ok"])

    def to_dict(self) -> dict:
        d = asdict(self)
        d["integrity_ok"] = self.integrity_ok
        return d

    def summary(self) -> list[str]:
        """Short bilingual lines for a message box: provenance first, integrity last."""
        if not self.has_manifest:
            return ["C2PA 출처 기록(콘텐츠 자격 증명)이 없습니다. / No C2PA Content Credentials."]
        # State first; the history only describes the document if the record still holds.
        lines = []
        lines.append(f"기록 상태 / Record state: {STATE_KO.get(self.state, self.state)} / {self.state}")
        if self.state == "Valid":
            lines.append("기록과 내용은 온전하나 기록자가 신뢰 목록에 없습니다. / "
                         "Record and content intact; the recording party is not on a trust list.")
        for f in self.failure:
            if not f.startswith("signingCredential.untrusted"):
                lines.append(f"실패 / Failure: {f}")
        if self.binding is not None and not self.binding["ok"]:
            lines.append("독립 해시 검사 불일치: 기록 이후 문서가 바뀌었습니다. / "
                         "Independent hash check: the document changed after it was recorded.")
        if self.history:
            if not self.integrity_ok:
                lines.append("아래는 마지막 기록의 내용이며 지금 문서와 맞지 않습니다. / "
                             "Below is the last record; it does not match the document as it is now.")
            first = self.history[-1]
            lines.append(f"출처 / Origin: {_who(first)}, {_when(first)}")
            lines.append(f"기록된 판 / Recorded versions: {len(self.history)}")
            for step in self.history:
                lines.append(f"  v{step['version']}  {_when(step)}  {_who(step)}")
                for a in step["actions"]:
                    extra = " — ".join(x for x in (a.get("tool"), a.get("description")) if x)
                    lines.append(f"      {a['action']}" + (f": {extra}" if extra else ""))
                for c in step["components"]:
                    own = (f"자체 출처 기록 / own credentials: {c.get('recorded_by') or '-'}"
                           if c["has_credentials"] else "출처 기록 없음 / no credentials")
                    lines.append(f"      구성요소 / component {c['title']}: {own}")
                if step["parent_problems"]:
                    lines.append("      이전 판 기록 문제 / problem in earlier record: "
                                 + ", ".join(step["parent_problems"]))
        return lines


def _when(step: dict) -> str:
    if not step.get("time"):
        return "-"
    return step["time"] + ("" if step.get("time_source") == "timestamp" else " (기록자 주장 / claimed)")


def _who(step: dict) -> str:
    by = step.get("recorded_by") or "-"
    return f"{by} ({step['issuer']})" if step.get("issuer") else by


def _collection_hash(detail: dict) -> dict | None:
    active = detail["manifests"][detail["active_manifest"]]
    store = active.get("assertion_store", {})
    return store.get("c2pa.hash.collection.data")


def _as_bytes(v) -> bytes:
    return base64.b64decode(v) if isinstance(v, str) else bytes(v)


def independent_check(data: bytes, reader: c2pa.Reader | None = None) -> dict | None:
    """Recompute the A.6 hashes without the SDK and compare them with the manifest."""
    reader = reader or _reader(data)
    coll = _collection_hash(json.loads(reader.detailed_json()))
    if coll is None:
        return None
    uris = coll["uris"]
    items = uris.items() if isinstance(uris, dict) else ((u["uri"], u) for u in uris)
    recorded = {u: (_as_bytes(v["hash"]), v.get("size")) for u, v in items}
    alg = coll.get("alg", "sha256")
    return compare(data, recorded, _as_bytes(coll.get("zip_central_directory_hash", b"")),
                   alg).to_dict()


def verify(data: bytes, trust: str | os.PathLike | None = None,
           independent: bool = True) -> VerifyResult:
    ensure_supported()
    result = VerifyResult(package=inspect_package(data).to_dict())
    try:
        reader = _reader(data, trust)
    except NoManifest:
        return result
    except Exception as exc:
        result.error = str(exc)
        return result
    result.state = reader.get_validation_state()
    active = (reader.get_validation_results() or {}).get("activeManifest", {})
    result.success = [x["code"] for x in active.get("success", [])]
    result.informational = [x["code"] for x in active.get("informational", [])]
    result.failure = [f'{x["code"]}: {x.get("explanation", "")}' for x in active.get("failure", [])]
    store = json.loads(reader.json())
    result.manifests_in_store = len(store.get("manifests", {}))
    result.history = history(store)
    m = reader.get_active_manifest() or {}
    result.title = m.get("title")
    gen = m.get("claim_generator_info") or []
    result.claim_generator = " ".join(f'{g.get("name", "")}/{g.get("version", "")}' for g in gen) or \
        m.get("claim_generator")
    sig = m.get("signature_info") or {}
    result.signer, result.issuer, result.signed_time = (sig.get("common_name"), sig.get("issuer"),
                                                        sig.get("time"))
    for a in m.get("assertions", []):
        if a.get("label", "").startswith("c2pa.actions"):
            result.actions += [x.get("action") for x in a.get("data", {}).get("actions", [])]
    for ing in m.get("ingredients", []):
        vr = (ing.get("validation_results") or {}).get("activeManifest", {})
        result.ingredients.append({
            "title": ing.get("title"), "relationship": ing.get("relationship"),
            "has_manifest": bool(ing.get("active_manifest")),
            "failure": [x["code"] for x in vr.get("failure", [])]})
    if independent:
        try:
            result.binding = independent_check(data, reader)
        except Exception as exc:  # malformed ZIP and the like
            result.binding = {"ok": False, "error": str(exc)}
    return result


def has_valid_binding(data: bytes) -> bool:
    """True if a manifest is present and its signature and hard binding still hold."""
    try:
        r = verify(data, independent=False)
    except Exception:
        return False
    return r.integrity_ok and "assertion.collectionHash.match" in r.success


# ------------------------------------------------------------------------- sign
def component_ingredients(data: bytes) -> list[tuple[str, str, bytes]]:
    """BinData parts that carry their own valid-format C2PA manifest."""
    found = []
    for name, part in bindata_parts(data):
        fmt = COMPONENT_FORMATS.get(name.rsplit(".", 1)[-1].lower())
        if fmt is None:
            continue
        try:
            c2pa.Reader(fmt, io.BytesIO(part))
        except Exception:
            continue
        found.append((name, fmt, part))
    return found


def build_definition(title: str, edited: bool, extra: dict | None = None, *,
                     application: dict | None = None, changes: dict | None = None,
                     note: str | None = None) -> dict:
    """Manifest definition: what was done (actions), with what, and what changed.

    application: the editor named in the package (softwareAgent of the action).
    changes: summary from provenance.diff_packages, stored as its own assertion.
    note: free text from the person recording the version (reason for the change).
    """
    description = [note] if note else []
    if changes is not None:
        description.append(" / ".join(describe_changes(changes)))
    if edited:
        # C2PA 2.x: the first action is c2pa.opened and names the parentOf ingredient.
        work = {"action": "c2pa.edited"}
        actions = [{"action": "c2pa.opened", "parameters": {"ingredientIds": [PARENT_LABEL]}}, work]
    else:
        work = {"action": "c2pa.created", "digitalSourceType": DIGITAL_CREATION}
        actions = [work]
    work["when"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # recorder's clock
    if application:
        work["softwareAgent"] = application
    if description:
        work["description"] = " — ".join(description)
    definition = {
        "claim_generator_info": [{"name": "hwpx-c2pa", "version": __version__}],
        "title": title,
        "format": OWPML_MIMETYPE,
        "assertions": [{"label": "c2pa.actions", "data": {"actions": actions}}],
    }
    if changes is not None:
        definition["assertions"].append({"label": CHANGES_LABEL, "data": changes})
    if extra:
        definition["assertions"] += extra.get("assertions", [])
        for k, v in extra.items():
            if k != "assertions":
                definition[k] = v
    return definition


def sign(data: bytes, signer: c2pa.Signer, *, title: str = "document.hwpx",
         parent: bytes | None = None, parent_title: str | None = None,
         components: bool = True, extra: dict | None = None, note: str | None = None) -> bytes:
    """Return a copy of an HWPX package with a signed provenance record for this version.

    The record states the editing application named in the package, the previous
    version (parentOf), what changed since then, pictures that carry their own
    credentials (componentOf), and an optional note.

    parent: the previous signed version. If omitted and ``data`` itself still has
    a valid credential, ``data`` is used as the parent, so signing twice chains.
    """
    ensure_supported()
    if parent is None and has_valid_binding(data):
        parent = data
    changes = diff_packages(parent, data) if parent is not None else None
    builder = c2pa.Builder(json.dumps(build_definition(
        title, parent is not None, extra, application=editing_application(data),
        changes=changes, note=note)))
    if parent is not None:
        builder.add_ingredient({"title": parent_title or f"{title} (previous)",
                                "relationship": "parentOf", "label": PARENT_LABEL},
                               ZIP_FORMAT, io.BytesIO(parent))
    if components:
        for name, fmt, part in component_ingredients(data):
            builder.add_ingredient({"title": name, "relationship": "componentOf"},
                                   fmt, io.BytesIO(part))
    out = io.BytesIO()
    builder.sign(signer, ZIP_FORMAT, io.BytesIO(data), out)
    return out.getvalue()


def write_atomically(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".hwpx-c2pa-tmp")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)  # e.g. the target is locked by the editor
        raise


def sign_file(path: str | os.PathLike, signer: c2pa.Signer, output: str | os.PathLike | None = None,
              *, parent: str | os.PathLike | None = None, components: bool = True,
              extra: dict | None = None, locked_fallback: bool = True,
              note: str | None = None, title: str | None = None) -> Path:
    """Sign a file in place (default) or into ``output``.

    If the file is locked (Hangul on Windows keeps saved files locked), the signed
    copy is written next to it as ``<name>.c2pa.hwpx`` when locked_fallback is set.
    """
    src = Path(path)
    data = src.read_bytes()
    parent_bytes = Path(parent).read_bytes() if parent else None
    target = Path(output) if output else src
    signed = sign(data, signer, title=title or target.name, parent=parent_bytes,
                  parent_title=Path(parent).name if parent else None,
                  components=components, extra=extra, note=note)
    try:
        write_atomically(target, signed)
    except PermissionError:
        if not locked_fallback:
            raise
        target = target.with_name(target.stem + ".c2pa" + target.suffix)
        write_atomically(target, signed)
    return target
