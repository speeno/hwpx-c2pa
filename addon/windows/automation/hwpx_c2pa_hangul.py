"""Hangul (Windows) helper: check C2PA credentials on open, re-sign after every save.

STATUS: experimental, NOT YET TESTED ON WINDOWS. Written against the Hancom HWP
Automation manual (HwpAutomation_2504):
  * IHwpObjectEvents: DocumentAfterOpen, DocumentBeforeSave, DocumentAfterSave,
    DocumentAfterClose (each passes a document ID)
  * XHwpDocuments.FindItem(id).FullName: full path of the document
  * section 1.5: attach to a running Hangul through the Running Object Table
    entry "!HwpObject.<version>"
  * XHwpMessageBox: String, Flag, DoModal

Flow
  open        : verify the credentials, remember the bytes of a valid version
  before save : remember the bytes on disk if they carry a valid credential
  after save  : sign the saved .hwpx; the remembered version becomes parentOf
  after close : sign files that were locked right after saving

Licence note: Hancom allows HWP Automation free of charge for personal,
non-commercial use only; commercial use needs Hancom's approval.
This helper only listens to events and never asks Hangul to open or save files,
so the automation security module (FilePathCheckDLL) is not required.

usage:
  pip install "hwpx-c2pa[windows]"
  hwpx-c2pa fetch-lib
  python hwpx_c2pa_hangul.py [--cert chain.pem --key signer.key] [--popup] [--no-sign]
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import pythoncom
import win32com.client

from hwpx_c2pa import engine
from hwpx_c2pa._paths import load_config

STATE = {"hwp": None, "signer": None, "trust": None, "popup": False, "sign": True,
         "previous": {}, "pending": {}}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def attach_running_hangul():
    """Automation object of a Hangul instance the user already opened, or None."""
    rot = pythoncom.GetRunningObjectTable()
    ctx = pythoncom.CreateBindCtx(0)
    for moniker in rot.EnumRunning():
        if moniker.GetDisplayName(ctx, None).startswith("!HwpObject"):
            unknown = rot.GetObject(moniker)
            return win32com.client.Dispatch(unknown.QueryInterface(pythoncom.IID_IDispatch))
    return None


def doc_path(doc_id) -> str:
    try:
        return STATE["hwp"].XHwpDocuments.FindItem(doc_id).FullName or ""
    except Exception:
        return ""


def show(text: str) -> None:
    log(text.replace("\n", " | "))
    if not STATE["popup"]:
        return
    try:
        box = STATE["hwp"].XHwpMessageBox
        box.String = text
        box.Flag = 0
        box.DoModal()
    except Exception as exc:
        log(f"message box failed: {exc}")


def sign_saved(path: str) -> None:
    data = Path(path).read_bytes()
    if engine.has_valid_binding(data):
        STATE["previous"][path] = data
        return
    parent = STATE["previous"].get(path)
    signed = engine.sign(data, STATE["signer"], title=os.path.basename(path), parent=parent,
                         parent_title=f"{os.path.basename(path)} (previous)")
    engine.write_atomically(Path(path), signed)  # PermissionError while Hangul locks the file
    STATE["previous"][path] = signed
    log(f"signed{' (chained to previous version)' if parent else ''}: {path}")


class HangulEvents:
    def OnDocumentAfterOpen(self, doc_id):
        path = doc_path(doc_id)
        if not path.lower().endswith(".hwpx") or not os.path.exists(path):
            return
        data = Path(path).read_bytes()
        result = engine.verify(data, trust=STATE["trust"])
        if result.integrity_ok:
            STATE["previous"][path] = data
        if result.has_manifest:
            show("C2PA\n" + "\n".join(result.summary()))

    def OnDocumentBeforeSave(self, doc_id):
        path = doc_path(doc_id)
        if path.lower().endswith(".hwpx") and os.path.exists(path):
            data = Path(path).read_bytes()
            if engine.has_valid_binding(data):
                STATE["previous"][path] = data

    def OnDocumentAfterSave(self, doc_id):
        path = doc_path(doc_id)
        if not STATE["sign"] or not path.lower().endswith(".hwpx"):
            return
        try:
            sign_saved(path)
        except PermissionError:
            STATE["pending"][doc_id] = path
            log(f"file locked; will sign after the document is closed: {path}")
        except Exception as exc:
            show(f"C2PA 서명 실패 / signing failed:\n{exc}")

    def OnDocumentAfterClose(self, doc_id):
        path = STATE["pending"].pop(doc_id, None)
        if path:
            time.sleep(0.5)
            try:
                sign_saved(path)
            except Exception as exc:
                log(f"signing after close failed: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cert"), ap.add_argument("--key"), ap.add_argument("--alg")
    ap.add_argument("--tsa"), ap.add_argument("--trust")
    ap.add_argument("--popup", action="store_true", help="show results in a Hangul message box")
    ap.add_argument("--no-sign", action="store_true", help="only verify on open")
    a = ap.parse_args()
    cfg = load_config()
    cert, key = a.cert or cfg.get("cert"), a.key or cfg.get("key")
    STATE["sign"] = not a.no_sign
    if STATE["sign"]:
        if not cert or not key:
            raise SystemExit("no signing certificate/key (use --cert/--key or the config file)")
        STATE["signer"] = engine.load_signer(cert, key, a.alg or cfg.get("alg", "es256"),
                                             a.tsa or cfg.get("tsa"))
    STATE["trust"], STATE["popup"] = a.trust or cfg.get("trust"), a.popup

    hwp = attach_running_hangul()
    if hwp is None:
        hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        hwp.XHwpWindows.Item(0).Visible = True
    STATE["hwp"] = hwp
    win32com.client.WithEvents(hwp, HangulEvents)
    log("listening to Hangul; Ctrl+C to stop")
    while True:
        pythoncom.PumpWaitingMessages()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
