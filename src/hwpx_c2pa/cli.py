"""Command line: hwpx-c2pa {sign, verify, history, view, report, check, watch, info, fetch-lib, dev-certs}.

Signer settings come from the options, else from the environment
(HWPX_C2PA_CERT, HWPX_C2PA_KEY, HWPX_C2PA_ALG, HWPX_C2PA_TSA, HWPX_C2PA_TRUST),
else from the config file (see ``hwpx-c2pa info``).

Exit codes of ``verify`` and ``check``: 0 intact, 1 invalid or mismatch,
2 no Content Credentials, 3 error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from ._paths import config_path, load_config


def _setting(args, name: str, env: str, default=None):
    value = getattr(args, name, None)
    if value:
        return value
    if os.environ.get(env):
        return os.environ[env]
    return load_config().get(name, default)


def _signer(args):
    from .engine import load_signer
    cert = _setting(args, "cert", "HWPX_C2PA_CERT")
    key = _setting(args, "key", "HWPX_C2PA_KEY")
    if not cert or not key:
        sys.exit("error: no signing certificate/key; use --cert/--key, HWPX_C2PA_CERT/KEY, "
                 f"or {config_path()}")
    return load_signer(cert, key, _setting(args, "alg", "HWPX_C2PA_ALG", "es256"),
                       _setting(args, "tsa", "HWPX_C2PA_TSA"))


def _emit(obj: dict, as_json: bool, lines: list[str]) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print("\n".join(lines))


def cmd_sign(args) -> int:
    from .engine import sign_file
    extra = json.loads(Path(args.manifest).read_text(encoding="utf-8")) if args.manifest else None
    out = sign_file(args.input, _signer(args), args.output, parent=args.parent,
                    components=not args.no_components, extra=extra, note=args.note)
    note = "" if out == Path(args.output or args.input) else " (file was locked; wrote a copy)"
    _emit({"signed": str(out), "locked_copy": bool(note)}, args.json, [f"signed: {out}{note}"])
    return 0


def cmd_verify(args) -> int:
    from .engine import verify
    data = Path(args.input).read_bytes()
    r = verify(data, trust=_setting(args, "trust", "HWPX_C2PA_TRUST"))
    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("\n".join(r.summary()))
    if r.error:
        return 3
    if not r.has_manifest:
        return 2
    return 0 if r.integrity_ok else 1


def cmd_history(args) -> int:
    """Origin and edit history only, oldest version first."""
    from .engine import verify
    r = verify(Path(args.input).read_bytes(), trust=_setting(args, "trust", "HWPX_C2PA_TRUST"))
    if args.json:
        print(json.dumps(r.history, ensure_ascii=False, indent=2))
    else:
        for step in reversed(r.history):
            claimed = "" if step.get("time_source") == "timestamp" else " (claimed)"
            print(f"v{step['version']}  {step.get('time') or '-'}{claimed}  {step.get('recorded_by') or '-'}"
                  f"  [{step.get('title')}]")
            for a in step["actions"]:
                extra = " — ".join(x for x in (a.get("tool"), a.get("description")) if x)
                print(f"    {a['action']}" + (f": {extra}" if extra else ""))
            for c in step["components"]:
                print(f"    component {c['title']}: "
                      + (f"own credentials by {c.get('recorded_by')}" if c["has_credentials"]
                         else "no credentials"))
        if not r.history:
            print("no Content Credentials")
    return _exit_code(r)


def _exit_code(r) -> int:
    if r.error:
        return 3
    if not r.has_manifest:
        return 2
    return 0 if r.integrity_ok else 1


def cmd_report(args) -> int:
    """view: open the verification window; report: write it to a file."""
    from . import report
    from .engine import verify
    src = Path(args.input)
    r = verify(src.read_bytes(), trust=_setting(args, "trust", "HWPX_C2PA_TRUST"))
    if args.cmd == "view":
        path = report.show(r, src.name)
    else:
        path = report.write(r, src.name, args.output)
    print(path)
    return _exit_code(r)


def cmd_check(args) -> int:
    from .engine import NoManifest, independent_check
    from .package import inspect_package
    data = Path(args.input).read_bytes()
    pkg = inspect_package(data)
    try:
        binding = independent_check(data)
    except NoManifest:
        binding = None
    result = {"package": pkg.to_dict(), "binding": binding}
    lines = [f"OWPML package: {'yes' if pkg.is_owpml else 'no'}",
             f"manifest entry: {'yes' if pkg.has_manifest_entry else 'no'}"]
    if binding:
        for e in binding["entries"]:
            lines.append(f"  {e['status']:16} {e['size']:8}  {e['uri']}")
        lines += [f"  {'missing':16} {'':8}  {m}" for m in binding["missing"]]
        lines.append(f"central directory: {binding['central_directory']}")
    lines += [f"problem: {p}" for p in pkg.problems] + [f"note: {n}" for n in pkg.notes]
    _emit(result, args.json, lines)
    if binding is None:
        return 2
    return 0 if binding["ok"] and not pkg.problems else 1


def cmd_watch(args) -> int:
    from .watch import watch
    try:
        watch(args.folder, _signer(args), cache=args.cache, interval=args.interval,
              recursive=args.recursive, components=not args.no_components, once=args.once)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_info(args) -> int:
    from . import _lib
    info = {"hwpx-c2pa": __version__,
            "c2pa-python": _pkg_version("c2pa-python"),
            "native library": _lib.c2pa.sdk_version(),
            "native library override": str(_lib.LIBRARY_OVERRIDE) if _lib.LIBRARY_OVERRIDE else None,
            "minimum native library": ".".join(map(str, _lib.MIN_LIBRARY)),
            "supported": _lib.library_version() >= _lib.MIN_LIBRARY,
            "config file": str(config_path())}
    _emit(info, args.json, [f"{k}: {v}" for k, v in info.items()])
    return 0 if info["supported"] else 1


def _pkg_version(name: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def cmd_fetch_lib(args) -> int:
    from .fetchlib import fetch
    fetch(force=args.force)
    return 0


def cmd_dev_certs(args) -> int:
    from .devcerts import create
    paths = create(args.outdir)
    for k, p in paths.items():
        print(f"{k}: {p}")
    print("TEST ONLY - do not use these certificates for real documents.")
    return 0


def _signer_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--cert", help="PEM certificate chain, leaf first")
    p.add_argument("--key", help="PEM private key")
    p.add_argument("--alg", help="es256 (default), es384, es512, ps256, ps384, ps512, ed25519")
    p.add_argument("--tsa", help="RFC 3161 time-stamp authority URL")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="hwpx-c2pa", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"hwpx-c2pa {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sign", aliases=["record"],
                       help="record this version: embed signed Content Credentials "
                            "(in place unless -o)")
    s.add_argument("--note", help="what was done in this version, in your words")
    s.add_argument("input"), s.add_argument("-o", "--output")
    s.add_argument("--parent", help="previous recorded version (parentOf): keeps the history")
    s.add_argument("--no-components", action="store_true",
                   help="do not link BinData parts that carry their own credentials")
    s.add_argument("--manifest", help="JSON with extra assertions / manifest fields")
    s.add_argument("--json", action="store_true")
    _signer_options(s)
    s.set_defaults(func=cmd_sign)

    v = sub.add_parser("verify", help="validate Content Credentials")
    v.add_argument("input"), v.add_argument("--trust", help="PEM trust anchors")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_verify)

    h = sub.add_parser("history", help="origin and edit history, version by version")
    h.add_argument("input"), h.add_argument("--trust"), h.add_argument("--json", action="store_true")
    h.set_defaults(func=cmd_history)

    vw = sub.add_parser("view", help="verification window: open the result in the browser")
    vw.add_argument("input"), vw.add_argument("--trust")
    vw.set_defaults(func=cmd_report)
    rp = sub.add_parser("report", help="write the verification page to an HTML file")
    rp.add_argument("input"), rp.add_argument("-o", "--output", required=True)
    rp.add_argument("--trust")
    rp.set_defaults(func=cmd_report)

    c = sub.add_parser("check", help="recompute the ZIP hard binding without the SDK")
    c.add_argument("input"), c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)

    w = sub.add_parser("watch", help="re-sign .hwpx files in a folder after each save")
    w.add_argument("folder"), w.add_argument("--cache")
    w.add_argument("--interval", type=float, default=2.0)
    w.add_argument("--recursive", action="store_true")
    w.add_argument("--no-components", action="store_true")
    w.add_argument("--once", action="store_true", help="scan once and exit")
    _signer_options(w)
    w.set_defaults(func=cmd_watch)

    i = sub.add_parser("info", help="versions, native library, config file")
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_info)

    f = sub.add_parser("fetch-lib", help="download a native C2PA library that handles HWPX")
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=cmd_fetch_lib)

    d = sub.add_parser("dev-certs", help="create TEST certificates (needs 'cryptography')")
    d.add_argument("outdir")
    d.set_defaults(func=cmd_dev_certs)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # report cleanly for add-ons that read stderr
        from ._lib import LibraryTooOld
        print(f"error: {exc}", file=sys.stderr)
        return 4 if isinstance(exc, LibraryTooOld) else 3


if __name__ == "__main__":
    sys.exit(main())
