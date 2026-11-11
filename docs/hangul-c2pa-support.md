# C2PA support in Hangul: problems and improvements

**English** | [한국어](hangul-c2pa-support.ko.md)

Checked with: Hancom Office HWP 12.30.0 (build 6544, macOS), C2PA Technical Specification 2.5, c2pa-rs 0.90.23 and 0.91.11, KS X 6101:2024, Hancom public documents (HWP Automation manual 2504, Addon Action guide, hwpx-owpml-model source). Hangul for Windows was not tested.

What matters in C2PA is not whether a file is signed but its **provenance and step-by-step edit history**. The problems and improvements below are judged by one question: can a Hangul document carry its own history without gaps, as testimony of the editing program? For the structure see [how-it-works.md](how-it-works.md).

## 1. Problems

| No. | Problem | What was observed | Effect |
|---|---|---|---|
| P1 | Saving removes the credentials | Hangul 12.30 (Mac) opens a signed HWPX without error. After one character is typed and the file saved, the package is rewritten and `META-INF/content_credential.c2pa` is gone | Document-level credentials and the version history are lost, with no notice to the user |
| P2 | No rule for unknown parts | KS X 6101 does not say whether a processor keeps or drops parts it does not know. Hancom's public model writes known parts only | Any extension part meets the same fate |
| P3 | Picture parts are renamed on save | `BinData/BIN0001.jpg` becomes `BinData/image1.jpeg`; the bytes are unchanged | The picture's own credentials survive, but names no longer match the URI list of the earlier manifest |
| P4 | Credentials are not shown on open | Nothing indicates that a document is signed | Recipients cannot see provenance |
| P5 | Post-save hooks differ by platform | Windows has automation events (`DocumentAfterSave`); the Mac version has neither automation nor add-ins | On Mac only an external folder watcher is possible |
| P6 | File lock after save (Windows) | The `lock` option of save/open defaults to TRUE (automation manual); whether it applies to HWPX was not verified | An external signer may be unable to rewrite the file right after the save |
| P7 | No registered media type | `application/hwp+zip` exists only inside the files, not at IANA; the C2PA SDK format list has no `.hwpx` | Tools do not recognise HWPX directly |
| P8 | Relation to the existing e-signature is undefined | Hancom's model source defines `META-INF/signatures.xml`, the KS X 6101 schemas do not. The Mac version does not support documents with certificate validation | Order and scope are unclear when both signatures are used |
| P9 | "Damaged or tampered" warnings | The Hancom forum reports a hand-edited HWPX being blocked. Files signed by this tool opened without warning on Mac; Windows was not checked | A signed file might fail to open |
| P10 | Add-in documentation is old | The User Action guide dates from 2008 and has no save event; the guide for the newer add-on method in 2024 is not public | Third parties cannot extend Hangul reliably |
| P11 | Recompression alone breaks credentials | C2PA A.6 hashes the compressed bytes | Not a Hangul defect, but it means every save must be followed by a new signature |
| P12 | The editing program cannot testify to the history itself | Today a tool outside Hangul records from the saved result. The editor name is copied from `version.xml`, and the changes are a summary from comparing two versions | The core of C2PA is the record of what was done, and that content remains a statement of the recording party. Anyone can rewrite `version.xml` |
| P13 | Actions during editing leave no trace | Pasting, inserting another document, replacing a picture, using AI features such as translation or summarising, accepting or rejecting tracked changes cannot be seen from the saved package | One can tell that three paragraphs changed between versions, not that they were pasted from another document or written by AI |
| P14 | Saves that are not recorded drop out of the history | A version saved without the add-on, or on another PC, has no record | The next change summary lumps several edits together; without the file of the previous version the history is cut |

## 2. Improvements

**a. Hangul (product)**

| No. | Improvement | Addresses |
|---|---|---|
| I1 | Do not drop a C2PA manifest silently on save; at least warn that saving removes the Content Credentials | P1 |
| I2 | Built-in signing: on save, add the previous manifest as the `parentOf` ingredient and create a new manifest; record what was done as actions (`c2pa.opened`, `c2pa.edited`, a `digitalSourceType` when AI features are used) | P1, P11 |
| I3 | Validate on open and show the result (document information or status bar); warn when invalid | P4 |
| I4 | Keep the credentials of inserted pictures and link them as `componentOf` ingredients; record it when a picture is re-encoded | P3 |
| I5 | Keep part names stable across saves | P3 |
| I6 | Until signing is built in: provide a post-save hook on every platform, with the file unlocked when the event fires, or a pre-write hook that hands over the package bytes. Offer the same interface on Mac | P5, P6 |
| I7 | Update the add-in documentation for current versions and publish the new add-on guide | P10 |
| I8 | Do not treat a package containing `META-INF/content_credential.c2pa` as damaged or tampered | P9 |
| I9 | On export to PDF, create a PDF manifest (C2PA A.4) with the HWPX credentials as an ingredient | Provenance survives conversion |
| I10 | Hangul becomes the recording party (claim generator). On save it creates the manifest under its own name and version and records the actions actually performed while editing: content brought in from another document (`c2pa.placed`, with that document as an ingredient), pictures inserted or replaced, format conversion (`c2pa.converted`), parts made with AI features (`digitalSourceType: trainedAlgorithmicMedia` and the like), tracked changes accepted or rejected | P12, P13 |
| I11 | Connect track changes and document history (version comparison) with the C2PA version chain: one manifest per version, each version of the document history linked as `parentOf` | P13, P14 |
| I12 | On open, offer a window that shows the origin and the history per version (who, when, with what, what was done). Showing only whether a signature is valid is not enough | P4 |

**b. OWPML standard (revision of KS X 6101)**

| No. | Improvement | Addresses |
|---|---|---|
| S1 | Reserve the part `META-INF/content_credential.c2pa` (media type `application/c2pa`) | P1, P2 |
| S2 | Processor rules: unknown parts are kept, or the user is told when they are dropped. The credentials part is re-signed, or chained into a new manifest, or removed with notice | P1, P2 |
| S3 | Standardise the XML signature part (`META-INF/signatures.xml`) and state that, when both are used, the XML signature comes first and the C2PA manifest second (as C2PA A.6.4 does for EPUB and OOXML) | P8 |
| S4 | Decide whether the manifest part is declared in `content.hpf` and `manifest.xml` | P2 |
| S5 | Define the media type `application/hwp+zip` in the standard and register it with IANA (standards tree, RFC 6838) | P7 |

**c. C2PA ecosystem**

| No. | Improvement | Addresses |
|---|---|---|
| E1 | Add `hwpx` and `application/hwp+zip` to the ZIP handler format list of c2pa-rs | P7 |
| E2 | Ship library 0.91.11 or later with c2pa-python | Removes the need for `fetch-lib` |
| E3 | Propose OWPML for the format table in Annex A.1 of the C2PA specification | P7 |
| E4 | Korean certification authorities on the C2PA trust list, or a trust list for public-sector documents | Real `Trusted` results |

## 3. What this repository covers

- Most of I2 and I4: re-signing after save, chaining to the previous version, linking picture credentials.
- Part of I3: command-line validation, and validation on open in the Windows add-on (not tested).
- I1, I5, I8, I9 and the standard and ecosystem items cannot be solved here; they need Hancom and the standard's revision.
