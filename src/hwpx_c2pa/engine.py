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
import io
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from ._lib import c2pa, ensure_supported
from .package import OWPML_MIMETYPE, bindata_parts, inspect_package
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
        """Short bilingual lines for a message box."""
        if not self.has_manifest:
            return ["C2PA 자격 증명이 없습니다. / No C2PA Content Credentials."]
        lines = [f"상태 / State: {STATE_KO.get(self.state, self.state)} / {self.state}"]
        if self.state == "Valid":
            lines.append("서명과 내용은 온전하나 서명자가 신뢰 목록에 없습니다. / "
                         "Signature and content intact; signer not on a trust list.")
        if self.signer or self.issuer:
            lines.append(f"서명자 / Signer: {self.signer or '-'} ({self.issuer or '-'})")
        if self.signed_time:
            lines.append(f"서명 시각 / Signed: {self.signed_time}")
        if self.actions:
            lines.append(f"동작 / Actions: {', '.join(self.actions)}")
        for ing in self.ingredients:
            lines.append(f"재료 / Ingredient: {ing['title']} ({ing['relationship']})")
        for f in self.failure:
            if not f.startswith("signingCredential.untrusted"):
                lines.append(f"실패 / Failure: {f}")
        if self.binding is not None and not self.binding["ok"]:
            lines.append("독립 해시 검사 불일치 / Independent hash check: mismatch")
        return lines


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


def build_definition(title: str, edited: bool, extra: dict | None = None) -> dict:
    if edited:
        # C2PA 2.x: the first action is c2pa.opened and names the parentOf ingredient.
        actions = [{"action": "c2pa.opened", "parameters": {"ingredientIds": [PARENT_LABEL]}},
                   {"action": "c2pa.edited"}]
    else:
        actions = [{"action": "c2pa.created", "digitalSourceType": DIGITAL_CREATION}]
    definition = {
        "claim_generator_info": [{"name": "hwpx-c2pa", "version": __version__}],
        "title": title,
        "format": OWPML_MIMETYPE,
        "assertions": [{"label": "c2pa.actions", "data": {"actions": actions}}],
    }
    if extra:
        definition["assertions"] += extra.get("assertions", [])
        for k, v in extra.items():
            if k != "assertions":
                definition[k] = v
    return definition


def sign(data: bytes, signer: c2pa.Signer, *, title: str = "document.hwpx",
         parent: bytes | None = None, parent_title: str | None = None,
         components: bool = True, extra: dict | None = None) -> bytes:
    """Return a signed copy of an HWPX package.

    parent: the previous signed version. If omitted and ``data`` itself still has
    a valid credential, ``data`` is used as the parent, so signing twice chains.
    """
    ensure_supported()
    if parent is None and has_valid_binding(data):
        parent = data
    builder = c2pa.Builder(json.dumps(build_definition(title, parent is not None, extra)))
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
    os.replace(tmp, path)


def sign_file(path: str | os.PathLike, signer: c2pa.Signer, output: str | os.PathLike | None = None,
              *, parent: str | os.PathLike | None = None, components: bool = True,
              extra: dict | None = None, locked_fallback: bool = True) -> Path:
    """Sign a file in place (default) or into ``output``.

    If the file is locked (Hangul on Windows keeps saved files locked), the signed
    copy is written next to it as ``<name>.c2pa.hwpx`` when locked_fallback is set.
    """
    src = Path(path)
    data = src.read_bytes()
    parent_bytes = Path(parent).read_bytes() if parent else None
    signed = sign(data, signer, title=src.name, parent=parent_bytes,
                  parent_title=Path(parent).name if parent else None,
                  components=components, extra=extra)
    target = Path(output) if output else src
    try:
        write_atomically(target, signed)
    except PermissionError:
        if not locked_fallback:
            raise
        target = src.with_name(src.stem + ".c2pa" + src.suffix)
        write_atomically(target, signed)
    return target
