# hwpx-c2pa

**English** | [한국어](README.ko.md)

**Engine and Hangul add-ons that record and show the provenance and edit history of HWPX (OWPML, KS X 6101) documents as C2PA Content Credentials**

Author: Dongsun Nam (speeno) · License: MIT · Status: alpha (0.1.0)

## About this project

- **Purpose.** C2PA is mostly known for images, video and other multimedia. This project was developed to confirm that C2PA can also be applied to another kind of digitally created object, the textual document, taking OWPML (HWPX) as the format, and to see how it can be used in practice.
- **Result.** It can. Content Credentials are embedded in and read from HWPX packages under Annex A.6 of the C2PA Technical Specification 2.5, without changing the OWPML schema, and a document carries its origin and edit history from version to version.
- **Findings for the Hangul software.** Several points in how Hangul is implemented need to change before this works without an add-on; the first is that saving a document removes the credentials. See [problems and improvements](docs/hangul-c2pa-support.md) (product items I1 to I12).
- **Findings for the OWPML standard.** Parts of the OWPML specification (KS X 6101) need revision, such as how a processor treats parts it does not know and how the credentials part is declared. See the same document (standard items S1 to S5).
- **How to use it.** The project is delivered in two forms: an **add-on for Hangul** and a **command line (CLI) tool**.

- How it works, with block diagrams: [docs/how-it-works.md](docs/how-it-works.md)
- Worked example with screens: [docs/case-study.md](docs/case-study.md)
- Korean and English samples: [samples/](samples/)
- Problems and improvements for C2PA support in Hangul: [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md)

## Preview

**1. Recording versions and reading the history** (`sign`, `history`): version 1 created, version 2 edited in Hangul, with what changed.

![Command line: record and history](docs/screenshots/01-cli-record-history.png)

**2. Provenance and edit history of a document** (`view`): who recorded each version, when, with which program, what changed since the previous version, and where the picture inside comes from.

![Provenance and edit history](docs/screenshots/06-view-edit-history-en-sample.png)

**3. A document changed without a record**: the history no longer describes the document, and the part that differs is marked.

![Does not match the record](docs/screenshots/05-view-changed-after-record.png)

**4. A document saved by Hangul without the add-on**: the record is gone.

![No record](docs/screenshots/03-view-after-hangul-save-no-record.png)

**5. In Hangul 2024 for Windows, with the add-in**: the "C2PA 출처" button opens the provenance window for the open document.

![Provenance window opened from Hangul](docs/screenshots/win-01-provenance-window.png)

**6. After Ctrl+S in Hangul**: the save is recorded as version 2 in the open document itself, with the editor (Hancom Office Hangul 13.0.0.4226) and what changed.

![Two versions after saving in Hangul](docs/screenshots/win-02-after-save-two-versions.png)

**7. After another edit and the ordinary Save button**: version 3, chained to version 2.

![Third version](docs/screenshots/win-03-third-version.png)

## Install the Hangul add-on

### Windows: add-in inside Hangul

Tested with Hangul 2024 (13.0.0.4226, 32-bit) on Windows 11. Needs this repository (clone or ZIP). No administrator rights.

```powershell
powershell -ExecutionPolicy Bypass -File addon\windows\install.ps1 -Dll path\to\HwpxC2paAddon.dll
```

The script installs Python 3.12 (only if missing) and the engine in a private environment, fetches the C2PA library, creates test certificates and settings, picks the 32-bit or 64-bit add-in DLL to match `Hwp.exe`, registers it for the current user (`HKCU\Software\Hnc\HwpUserAction\Modules`), copies the samples to `Documents\hwpx-c2pa-samples` and puts a shortcut **Hangul C2PA** on the desktop. The DLL is built by CI (artifacts `HwpxC2paAddon-Win32` and `HwpxC2paAddon-x64` of the `test` workflow); without `-Dll` the script takes it from the latest release.

**Start Hangul with the "Hangul C2PA" shortcut** (or `hwpx-c2pa hangul [file]`). Hangul loads this kind of add-in only when a program asks it to through HWP Automation, so a Hangul started in the usual way does not show it.

What the add-in does in Hangul:

| In Hangul | What happens |
|---|---|
| Button **C2PA 출처** | Opens the provenance window: origin, edit history per version, pictures, hash check |
| **Save** (Ctrl+S, Save button, File menu) and button **C2PA 저장** | Saves, then records the saved version in the open document: editor, change summary, previous version chained |
| **Save as** | Hangul's own dialog, then the new file is recorded with the old file as its previous version |
| Documents that are not HWPX | Saved as usual, nothing recorded |

- Saving is taken over with `ReplaceAction`. To leave Hangul's own Save alone, set `HKCU\Software\hwpx-c2pa\ReplaceSave` (DWORD) to 0 and use the button.
- Hangul keeps the file of an open document locked. The add-in saves a temporary copy first, which releases the lock, and then puts the recorded file in place of the document.
- The last recorded version of each document is kept under `%LOCALAPPDATA%\hwpx-c2pa\parents`. If a save bypasses the add-in and Hangul drops the record, the next recorded save still chains to that copy.
- Not yet tested: the `install.ps1` in this repository as a whole (its steps were run on the test machine in an earlier form), 64-bit Hangul, Hangul 2020 and 2022, and "Save as". To remove: `addon\windows\useraction\register.ps1 -Remove`.

### macOS, or without an add-in: folder watcher

Hangul for Mac has no add-in interface. The watcher records every `.hwpx` saved in a folder as a new version:

```bash
pip install "hwpx-c2pa[devcerts] @ git+https://github.com/speeno/hwpx-c2pa" && hwpx-c2pa fetch-lib
hwpx-c2pa watch ~/Documents/Recorded --cert certs/signer-chain.pem --key certs/signer.key
```

## What it does

C2PA is a **provenance** record, not a signing feature. It lets a document carry where it came from and who did what, with which program, at each version. The signature and the hashes are the means of showing that this record has not been altered.

What this tool records for each version:

- **Who and when**: the recording party (certificate) and the time (time-stamp, else the time stated by the recorder).
- **With what**: the program that made or edited the document (name and version from `version.xml` in the package).
- **What was done**: created (`c2pa.created`), or previous version opened and edited (`c2pa.opened`, `c2pa.edited`), plus a note from the recorder (`--note`).
- **What changed**: a summary against the previous version (body paragraphs modified, added, removed; character count; parts changed). Counts and part names only, never the text.
- **Which version it derives from**: the record of the previous version is chained as `parentOf`, so the last file alone shows the whole history.
- **Where the pictures inside come from**: a picture that carries its own C2PA record (camera, drawing tool, generative AI and so on) is linked as `componentOf`.

For checking, `history` and `view` show this history version by version and, if the document changed after it was recorded, which part differs.

Technical basis: Annex A.6 (ZIP-based formats) of the C2PA Technical Specification 2.5. The record is one added part, `META-INF/content_credential.c2pa`; the OWPML schema is not changed. The record is built and signed by the official C2PA SDK (c2pa-rs through c2pa-python), and the hashes are recomputed independently for cross-checking (`check`). Hangul removes the part on save, so the add-ons record a new version after each save. See [docs/how-it-works.md](docs/how-it-works.md) for the structure.

## Install

```bash
pip install git+https://github.com/speeno/hwpx-c2pa
hwpx-c2pa fetch-lib     # fetch a C2PA library (0.91.11) that can process HWPX
hwpx-c2pa info          # expect "supported: True"
```

Why `fetch-lib`: the library bundled with c2pa-python 0.38.2 (0.91.6) cannot process Deflate-compressed ZIP entries, and every HWPX file uses Deflate. `fetch-lib` downloads the library from the official c2pa-rs release, checks its SHA-256, and stores it in the user cache.

## Use

```bash
# test certificates (never use them for real documents)
pip install "hwpx-c2pa[devcerts] @ git+https://github.com/speeno/hwpx-c2pa"
hwpx-c2pa dev-certs ./certs

# record the first version (sign and record are the same command)
hwpx-c2pa sign report.hwpx --note "First draft" --cert certs/signer-chain.pem --key certs/signer.key
# record an edited version: chains to the previous one and stores a change summary
hwpx-c2pa sign v2.hwpx --parent v1.hwpx --note "Budget in clause 3 revised" ...
hwpx-c2pa history v2.hwpx                  # origin and edit history per version
hwpx-c2pa view v2.hwpx --trust certs/root-ca.pem     # provenance and history window (browser)
hwpx-c2pa verify v2.hwpx --trust certs/root-ca.pem   # summary and exit code
hwpx-c2pa check v2.hwpx                    # recompute the hashes without the SDK
hwpx-c2pa watch ~/Documents/Signed         # watch a folder, record a new version after each save
```

- `verify` exit codes: 0 intact, 1 invalid (tampered), 2 no credentials, 3 error.
- States: `Trusted` (record intact, recording party on a trust list), `Valid` (record intact, recording party not on a trust list), `Invalid` (the document changed after the record, or the record is damaged).
- The editor name and the change summary are statements of the recording party, not of Hangul itself ([docs/how-it-works.md](docs/how-it-works.md), clause 5).
- To avoid passing the certificate and key each time, use the config file (`hwpx-c2pa info` prints its location):

```json
{"cert": "/path/signer-chain.pem", "key": "/path/signer.key", "tsa": "http://timestamp.example", "trust": "/path/anchors.pem"}
```

From Python:

```python
from hwpx_c2pa import load_signer, sign, verify
signer = load_signer("signer-chain.pem", "signer.key")
v1 = sign(open("report.hwpx", "rb").read(), signer, title="report.hwpx", note="First draft")
v2 = sign(open("edited.hwpx", "rb").read(), signer, title="report.hwpx", parent=v1, note="Budget revised")
for step in verify(v2).history:      # newest first
    print(step["version"], step["time"], step["recorded_by"], step["actions"], step["changes"])
```

## Hangul add-ons

| Add-on | Platform | What it does | Test status |
|---|---|---|---|
| `hwpx-c2pa watch`, `addon/macos/install-watch.sh` | macOS, Windows, Linux | Watches a folder and records each saved `.hwpx` as a new version (previous version chained, change summary). Needs no Hangul API | Tested, including files saved by Hangul 12.30 for Mac |
| `addon/windows/automation/hwpx_c2pa_hangul.py` | Windows, Hangul 2020+ | Attaches to the running Hangul, shows the provenance on open, records a new version right after save (HWP Automation events) | **Not tested** |
| `addon/windows/useraction/` (C++ DLL) + `hwpx-c2pa hangul` | Windows | Hangul add-in (User Action Module): buttons, provenance window, every save recorded in the open document | Tested with Hangul 2024 (13.0.0.4226, 32-bit): versions 1 to 3 recorded through Ctrl+S and the Save button |

- Hangul for Mac has no add-in or automation interface, so the folder watcher is the only route there.
- Hancom allows HWP Automation free of charge for personal, non-commercial use only; commercial use needs Hancom's approval. The MIT licence of this repository covers this repository's code only.
- The Windows add-in was written from Hancom's public documents (HWP Automation manual, Addon Action guide of 2008) and corrected in tests with Hangul 2024. What differs from the guide is noted in `addon/windows/useraction/src/HncUserAction.h`.

## Known limits

- Real trust needs a certificate from a CA on the C2PA trust list or from an organisational PKI. Test certificates reach `Valid` only.
- Rewriting the ZIP (recompressing, saving with another program) breaks the match with the record even if the content is the same. The specification defines it so.
- A save that was not recorded leaves no trace in the history. The change summary is the difference between two recorded versions.
- The time is vouched for by a third party only when a time-stamp authority (`--tsa`) is used; otherwise it is shown as stated by the recorder.
- The C2PA SDK does not know `.hwpx` or `application/hwp+zip`; this tool passes packages as generic ZIP. To inspect a file with c2patool, rename it to `.zip`.
- SDK 0.90.x (c2patool 0.27.23) cannot read files signed by 0.91.
- Each version carries the earlier manifests, so files grow with the history.
- ZIP64 and encrypted (distribution) documents are not handled.

What Hangul itself would need in order to support C2PA is described in [docs/hangul-c2pa-support.md](docs/hangul-c2pa-support.md).

## Development

```bash
pip install -e ".[dev]" && hwpx-c2pa fetch-lib && pytest -q
```

The tests build a synthetic OWPML-shaped package; no Hancom software or sample documents are needed.

## References

- C2PA Technical Specification 2.5, Annex A.6: https://spec.c2pa.org/specifications/specifications/2.5/specs/C2PA_Specification.html
- c2pa-rs: https://github.com/contentauth/c2pa-rs · c2pa-python: https://github.com/contentauth/c2pa-python
- KS X 6101:2024 (OWPML)
- Hancom HWP Automation: https://developer.hancom.com/hwpautomation · manuals: https://github.com/hancom-io/devcenter-archive

"한글", "한컴오피스", "HWP", "HWPX" are names or trademarks of Hancom Inc. This project is independent of Hancom and of the C2PA.
