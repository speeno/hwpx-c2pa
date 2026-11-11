// hwpx-c2pa add-on for Hangul (Windows): a User Action Module.
//
// STATUS: experimental. Hangul 2024 (13.0.0.4226) loads the module and calls it; see README. Written against
// Hancom's "Addon Action" guide (2008) and the HWP Automation manual (2504).
//
// Actions
//   HwpxC2paSaveSign : save the active document, then record it as a new version in its
//                      Content Credentials (editor, change summary; the version on disk
//                      before the save becomes the parentOf ingredient)
//   HwpxC2paVerify   : show the provenance and edit history of the active document
//   HwpxC2paSaveAs   : Hangul's "save as" dialog, then the same recording
//   HwpxC2paToolbar  : add a toolbar with the two buttons above
//
// The C2PA work is done by the hwpx-c2pa command line tool (Python), started as
// a child process, so this DLL has no C2PA or Python dependency of its own.
// The tool is looked up in HKCU\Software\hwpx-c2pa\Cli (REG_SZ), else on PATH.
//
// Copyright (c) 2026 Dongsun Nam (speeno). MIT License.
#include <windows.h>
#include <cstring>
#include <cwchar>
#include <cwctype>
#include <initializer_list>
#include <string>

#include "Dispatch.h"
#include "HncUserAction.h"

namespace {

const char* kActions[] = {"HwpxC2paSaveSign", "HwpxC2paVerify", "HwpxC2paToolbar", "HwpxC2paSaveAs"};
const wchar_t* kSerializePath = L"hwpx-c2pa\\toolbar_v3";
bool g_toolbarCreated = false;  // once per process: both load events report a new layout

std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), &w[0], n);
    return w;
}

// Appends a line to %LOCALAPPDATA%\\hwpx-c2pa\\addon-log.txt: shows whether and how Hangul calls the module.
void Trace(const wchar_t* what, const wchar_t* detail = L"") {
    wchar_t dir[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", dir, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    std::wstring path = std::wstring(dir) + L"\\hwpx-c2pa\\addon-log.txt";
    HANDLE h = CreateFileW(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                           OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    SYSTEMTIME t;
    GetLocalTime(&t);
    wchar_t line[512];
    int len = swprintf(line, 512, L"%02d:%02d:%02d pid %lu %ls %ls\r\n", t.wHour, t.wMinute, t.wSecond,
                       GetCurrentProcessId(), what, detail);
    if (len > 0) {
        char utf8[1536];
        int m = WideCharToMultiByte(CP_UTF8, 0, line, len, utf8, sizeof(utf8), nullptr, nullptr);
        DWORD written = 0;
        WriteFile(h, utf8, (DWORD)m, &written, nullptr);
    }
    CloseHandle(h);
}

// Button images, drawn here so the add-in needs no image files. Hangul wants a 32-bit
// strip of 16x16 cells, 60 cells wide (960 px), colours premultiplied by alpha.
//   . transparent   o outline   w paper   g green (recorded)   b blue (look)   W white
const char* kIconRecord[16] = {
    "..oooooooo......",
    "..owwwwwwoo.....",
    "..owwwwwwwo.....",
    "..owoooowwo.....",
    "..owwwwwwwo.....",
    "..owoooowwo.....",
    "..owwwwwwwo.....",
    "..owooowwggggg..",
    "..owwwwwgggggWg.",
    "..owwwwwggggWgg.",
    "..owwwwwgWgWggg.",
    "..owwwwwggWgggg.",
    "..oooooogggggg..",
    ".........gggg...",
    "................",
    "................"};
const char* kIconProvenance[16] = {
    "..oooooooo......",
    "..owwwwwwoo.....",
    "..owwwwwwwo.....",
    "..owoooowwo.....",
    "..owwwwwwwo.....",
    "..owoooobbbb....",
    "..owwwwbwwwwb...",
    "..owoobwwwwwwb..",
    "..owwwbwwwwwwb..",
    "..owwwbwwwwwwb..",
    "..owwwwbwwwwb...",
    "..oooooobbbbb...",
    "............bb..",
    ".............bb.",
    "..............b.",
    "................"};
HBITMAP g_buttons = nullptr;

DWORD IconColour(char ch) {  // 0xAARRGGBB, opaque colours need no premultiplying
    switch (ch) {
        case 'o': return 0xFF3B4A5A;
        case 'w': case 'W': return 0xFFFFFFFF;
        case 'g': return 0xFF1A7F4B;
        case 'b': return 0xFF1F6FEB;
        default: return 0x00000000;
    }
}

HBITMAP ButtonStrip() {
    if (g_buttons) return g_buttons;
    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof(bi.bmiHeader);
    bi.bmiHeader.biWidth = 16 * 60;
    bi.bmiHeader.biHeight = -16;  // top-down
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    DWORD* px = nullptr;
    g_buttons = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, (void**)&px, nullptr, 0);
    if (!g_buttons || !px) return nullptr;
    memset(px, 0, 16 * 60 * 16 * sizeof(DWORD));
    const char* const* icons[] = {kIconRecord, kIconProvenance};
    for (int n = 0; n < 2; ++n)
        for (int y = 0; y < 16; ++y)
            for (int x = 0; x < 16; ++x) px[y * 16 * 60 + n * 16 + x] = IconColour(icons[n][y][x]);
    return g_buttons;
}

std::wstring CliPath() {
    wchar_t buf[MAX_PATH * 2];
    DWORD size = sizeof(buf);
    if (RegGetValueW(HKEY_CURRENT_USER, L"Software\\hwpx-c2pa", L"Cli", RRF_RT_REG_SZ, nullptr,
                     buf, &size) == ERROR_SUCCESS && buf[0]) {
        return buf;
    }
    return L"hwpx-c2pa.exe";
}

// Runs "hwpx-c2pa <args>", captures stdout+stderr (UTF-8). Returns the exit code, -1 on failure.
int RunCli(const std::wstring& args, std::wstring* output) {
    SECURITY_ATTRIBUTES sa = {sizeof(sa), nullptr, TRUE};
    HANDLE rd = nullptr, wr = nullptr;
    if (!CreatePipe(&rd, &wr, &sa, 0)) return -1;
    SetHandleInformation(rd, HANDLE_FLAG_INHERIT, 0);

    SetEnvironmentVariableW(L"PYTHONUTF8", L"1");  // child prints UTF-8
    std::wstring cmd = L"\"" + CliPath() + L"\" " + args;
    STARTUPINFOW si = {sizeof(si)};
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = wr;
    si.hStdError = wr;
    PROCESS_INFORMATION pi = {};
    BOOL ok = CreateProcessW(nullptr, &cmd[0], nullptr, nullptr, TRUE, CREATE_NO_WINDOW, nullptr,
                             nullptr, &si, &pi);
    CloseHandle(wr);
    if (!ok) {
        CloseHandle(rd);
        return -1;
    }
    std::string raw;
    char chunk[4096];
    DWORD got = 0;
    while (ReadFile(rd, chunk, sizeof(chunk), &got, nullptr) && got > 0) raw.append(chunk, got);
    CloseHandle(rd);
    WaitForSingleObject(pi.hProcess, 120000);
    DWORD code = (DWORD)-1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    if (output) *output = Utf8ToWide(raw);
    return (int)code;
}

std::wstring Quote(const std::wstring& path) { return L"\"" + path + L"\""; }

bool IsHwpx(const std::wstring& path) {
    return path.size() > 5 && _wcsicmp(path.c_str() + path.size() - 5, L".hwpx") == 0;
}

void Notify(const std::wstring& text, UINT icon = MB_ICONINFORMATION) {
    MessageBoxW(GetActiveWindow(), text.c_str(), L"hwpx-c2pa", MB_OK | icon);
}

disp::Ptr ActiveDocument(IDispatch* hwp) {
    disp::Ptr docs = disp::GetObject(hwp, L"XHwpDocuments");
    return docs ? disp::GetObject(docs.get(), L"Active_XHwpDocument") : disp::Ptr();
}

const wchar_t* kCliMissing =
    L"hwpx-c2pa 명령을 실행할 수 없습니다. 설치 후 다시 시도하십시오.\n"
    L"Cannot run the hwpx-c2pa tool. Install it (pip install hwpx-c2pa) and try again.";

// Calls obj.method(s1, s2, ...) with string arguments; true if the call succeeded and
// did not return FALSE.
bool CallStrings(IDispatch* obj, const wchar_t* method, std::initializer_list<const wchar_t*> strs) {
    VARIANT args[4];
    UINT n = (UINT)strs.size();
    if (n > 4) return false;
    UINT i = n;
    for (const wchar_t* str : strs) {  // IDispatch takes arguments in reverse order
        --i;
        VariantInit(&args[i]);
        args[i].vt = VT_BSTR;
        args[i].bstrVal = SysAllocString(str);
    }
    VARIANT result;
    VariantInit(&result);
    HRESULT hr = disp::Invoke(obj, method, DISPATCH_METHOD, args, n, &result);
    for (UINT k = 0; k < n; ++k) VariantClear(&args[k]);
    bool ok = SUCCEEDED(hr) && !(result.vt == VT_BOOL && result.boolVal == VARIANT_FALSE);
    VariantClear(&result);
    return ok;
}

// HKCU\\Software\\hwpx-c2pa\\ReplaceSave (DWORD): 0 leaves Hangul's own Save alone. Default 1.
bool ReplaceSaveEnabled() {
    DWORD value = 1, size = sizeof(value);
    RegGetValueW(HKEY_CURRENT_USER, L"Software\\hwpx-c2pa", L"ReplaceSave", RRF_RT_REG_DWORD, nullptr,
                 &value, &size);
    return value != 0;
}

// Save (menu, toolbar, Ctrl+S) becomes "save and record". ReplaceAction only redirects
// menu and shortcut calls; HAction.Run("FileSave") still runs Hangul's own save.
void ReplaceSave(IDispatch* hwp) {
    if (!ReplaceSaveEnabled()) return;
    // Hangul has two IDs for each (FileSave / FileSave_S, FileSaveAs / FileSaveAs_S).
    const wchar_t* pairs[][2] = {{L"FileSave", L"HwpxC2paSaveSign"}, {L"FileSave_S", L"HwpxC2paSaveSign"},
                                 {L"FileSaveAs", L"HwpxC2paSaveAs"}, {L"FileSaveAs_S", L"HwpxC2paSaveAs"}};
    for (auto& p : pairs) {
        bool ok = CallStrings(hwp, L"ReplaceAction", {p[0], p[1]});
        Trace(p[0], ok ? L"replaced" : L"not replaced");
    }
}

bool RunBuiltIn(IDispatch* hwp, const wchar_t* action) {
    disp::Ptr haction = disp::GetObject(hwp, L"HAction");
    return haction && CallStrings(haction.get(), L"Run", {action});
}

// The open document is locked by Hangul, so the record went into <name>.c2pa.hwpx.
// Offer to close the document, put that file in its place and open it again, so
// that the document the user works on is the one that carries the record.
void SwapInRecordedCopy(IDispatch* hwp, IDispatch* doc, const std::wstring& path) {
    std::wstring copy = path.substr(0, path.size() - 5) + L".c2pa.hwpx";
    int answer = MessageBoxW(GetActiveWindow(),
        L"이 판의 출처 기록을 만들었습니다. 문서 파일이 한글에 열려 있어 기록은 사본에 들어 있습니다.\n"
        L"문서를 닫고 기록이 든 파일로 바꾼 뒤 다시 열까요?\n\n"
        L"The provenance record for this version was created. The document file is open in "
        L"Hangul, so the record is in a copy.\nClose the document, replace it with the recorded "
        L"file and open it again?",
        L"hwpx-c2pa", MB_YESNO | MB_ICONQUESTION);
    if (answer != IDYES) {
        Notify(L"기록이 든 사본 / Copy with the record:\n" + copy);
        return;
    }
    bool closed = disp::CallBool(doc, L"Close", false);
    Trace(L"swap: close", closed ? L"ok" : L"failed");
    BOOL moved = FALSE;
    for (int i = 0; i < 10 && !moved; ++i) {  // the lock is released shortly after the close
        moved = MoveFileExW(copy.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING);
        if (!moved) Sleep(200);
    }
    Trace(L"swap: replace", moved ? L"ok" : L"failed");
    VARIANT args[3];  // Open(path, format, arg), arguments in reverse order
    for (VARIANT& v : args) VariantInit(&v);
    args[2].vt = VT_BSTR; args[2].bstrVal = SysAllocString(path.c_str());
    args[1].vt = VT_BSTR; args[1].bstrVal = SysAllocString(L"HWPX");
    args[0].vt = VT_BSTR; args[0].bstrVal = SysAllocString(L"");
    HRESULT hr = disp::Invoke(hwp, L"Open", DISPATCH_METHOD, args, 3, nullptr);
    for (VARIANT& v : args) VariantClear(&v);
    Trace(L"swap: reopen", SUCCEEDED(hr) ? L"ok" : L"failed");
    if (!moved) Notify(L"파일을 바꾸지 못했습니다. 기록이 든 사본 / Could not replace the file. Copy with the record:\n" + copy,
                       MB_ICONWARNING);
}

// A copy of the last recorded version of each document, kept outside the document
// folder. If a save bypasses the add-in (Hangul then drops the record), the next
// recorded save still chains to this copy instead of starting a new history.
std::wstring StashPath(const std::wstring& docPath) {
    wchar_t dir[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", dir, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return L"";
    std::wstring folder = std::wstring(dir) + L"\\hwpx-c2pa\\parents";
    CreateDirectoryW(folder.c_str(), nullptr);
    unsigned long long h = 1469598103934665603ULL;  // FNV-1a over the lower-cased path
    for (wchar_t c : docPath) {
        h ^= (unsigned long long)towlower(c);
        h *= 1099511628211ULL;
    }
    wchar_t name[32];
    swprintf(name, 32, L"%016llx.hwpx", h);
    return folder + L"\\" + name;
}

bool HasIntactRecord(const std::wstring& file) { return RunCli(L"verify " + Quote(file), nullptr) == 0; }

std::wstring TempHwpx(const wchar_t* prefix) {
    wchar_t dir[MAX_PATH], tmp[MAX_PATH];
    GetTempPathW(MAX_PATH, dir);
    if (!GetTempFileNameW(dir, prefix, 0, tmp)) return L"";
    return tmp;  // an empty file with a .tmp name; the content decides, not the extension
}

FILETIME WriteTime(const std::wstring& file) {
    WIN32_FILE_ATTRIBUTE_DATA d = {};
    GetFileAttributesExW(file.c_str(), GetFileExInfoStandard, &d);
    return d.ftLastWriteTime;
}

// Save, then record the saved version in the document's Content Credentials.
//
// What the first tests with Hangul 2024 showed, and what this follows:
//  * Hangul keeps the file of an open document locked, also after SaveAs(path, "lock:false").
//  * SaveAs to ANOTHER path with "lock:false" writes a copy, leaves the document bound to
//    its own path and releases the lock on it.
// So the document is written to a temporary copy, and the recorded result is put in
// place of the document file, which is free at that moment.
int SaveAndSign(IDispatch* hwp, bool saveAs) {
    disp::Ptr doc = ActiveDocument(hwp);
    if (!doc) return 0;
    std::wstring before = disp::GetString(doc.get(), L"FullName");

    // The previous version: the file on disk if its record is intact, else the stash.
    std::wstring parentCopy;
    if (IsHwpx(before) && GetFileAttributesW(before.c_str()) != INVALID_FILE_ATTRIBUTES) {
        std::wstring tmp = TempHwpx(L"c2p");
        if (!tmp.empty() && CopyFileW(before.c_str(), tmp.c_str(), FALSE) && HasIntactRecord(tmp)) {
            parentCopy = tmp;
        } else {
            std::wstring stash = StashPath(before);
            if (!tmp.empty() && !stash.empty() && CopyFileW(stash.c_str(), tmp.c_str(), FALSE) &&
                HasIntactRecord(tmp)) {
                parentCopy = tmp;
                Trace(L"parent", L"from stash");
            } else if (!tmp.empty()) {
                DeleteFileW(tmp.c_str());
            }
        }
    }

    // Documents without a name or in another format, and "save as", go through Hangul's
    // own dialogs first. Run() is not redirected by ReplaceAction, so this does not loop.
    if (saveAs || !IsHwpx(before)) {
        FILETIME t0 = WriteTime(before);
        const wchar_t* own = saveAs ? L"FileSaveAs_S" : L"FileSave_S";
        bool ran = RunBuiltIn(hwp, own) || RunBuiltIn(hwp, saveAs ? L"FileSaveAs" : L"FileSave");
        Trace(saveAs ? L"built-in save as" : L"built-in save", ran ? L"ok" : L"failed");
        doc = ActiveDocument(hwp);
        std::wstring now = doc ? disp::GetString(doc.get(), L"FullName") : L"";
        FILETIME t1 = WriteTime(now);
        bool written = _wcsicmp(now.c_str(), before.c_str()) != 0 || CompareFileTime(&t0, &t1) != 0;
        if (!ran || !written || !IsHwpx(now)) {  // cancelled, failed, or not an HWPX document
            if (!parentCopy.empty()) DeleteFileW(parentCopy.c_str());
            return ran ? 1 : 0;
        }
        before = now;
    }
    const std::wstring path = before;

    int result = 0;
    std::wstring work = TempHwpx(L"c2w");
    bool saved = !work.empty() && CallStrings(hwp, L"SaveAs", {work.c_str(), L"HWPX", L"lock:false"});
    Trace(L"SaveAs temporary copy", saved ? L"ok" : L"failed");
    doc = ActiveDocument(hwp);
    std::wstring bound = doc ? disp::GetString(doc.get(), L"FullName") : L"";
    Trace(L"document bound to", bound.c_str());
    if (!saved) {
        Notify(L"문서를 저장하지 못했습니다. / The document could not be saved.", MB_ICONERROR);
    } else {
        std::wstring title = path.substr(path.find_last_of(L"\\/") + 1);
        std::wstring args = L"sign " + Quote(work) + L" -o " + Quote(path) + L" --title " + Quote(title);
        if (!parentCopy.empty()) args += L" --parent " + Quote(parentCopy);
        std::wstring out;
        int code = RunCli(args, &out);
        Trace(L"sign exit", std::to_wstring(code).c_str());
        if (code == -1) {
            Notify(kCliMissing, MB_ICONERROR);
        } else if (code != 0) {
            Notify(L"C2PA 기록 실패 / recording failed\n\n" + out, MB_ICONERROR);
        } else if (out.find(L"locked") != std::wstring::npos) {
            Trace(L"target still locked");
            SwapInRecordedCopy(hwp, doc.get(), path);
            result = 1;
        } else {
            result = 1;
            if (_wcsicmp(bound.c_str(), path.c_str()) != 0) {
                // Hangul re-bound the document to the temporary copy: bring it back.
                Trace(L"re-open original");
                if (doc) disp::CallBool(doc.get(), L"Close", false);
                CallStrings(hwp, L"Open", {path.c_str(), L"HWPX", L"lock:false"});
            } else if (doc) {
                disp::PutLong(doc.get(), L"Modified", 0);  // the file on disk is this version
            }
            std::wstring stash = StashPath(path);
            if (!stash.empty()) CopyFileW(path.c_str(), stash.c_str(), FALSE);
        }
    }
    if (!work.empty()) DeleteFileW(work.c_str());
    if (!parentCopy.empty()) DeleteFileW(parentCopy.c_str());
    return result;
}

int Verify(IDispatch* hwp) {
    disp::Ptr doc = ActiveDocument(hwp);
    if (!doc) return 0;
    std::wstring path = disp::GetString(doc.get(), L"FullName");
    if (!IsHwpx(path)) {
        Notify(L"저장된 HWPX 문서가 아닙니다.\nNot a saved HWPX document.", MB_ICONWARNING);
        return 0;
    }
    // The provenance window: a page with origin, edit history and components, opened as
    // its own window (see report.py). Exit codes 0 to 2 mean the page was shown.
    std::wstring out;
    int code = RunCli(L"view --app " + Quote(path), &out);
    Trace(L"view exit", std::to_wstring(code).c_str());
    if (code == -1) {
        Notify(kCliMissing, MB_ICONERROR);
        return 0;
    }
    if (code == 0) {  // remember this recorded version as a possible previous version
        std::wstring stash = StashPath(path);
        if (!stash.empty()) CopyFileW(path.c_str(), stash.c_str(), FALSE);
    }
    if (code > 2) Notify(L"출처를 확인하지 못했습니다 / could not read the provenance\n\n" + out, MB_ICONERROR);
    return 1;
}

// Toolbar, as in the Addon Action guide: XHwpWindows.Active_XHwpWindow.XHwpToolbarLayout.
int InstallToolbar(IDispatch* hwp) {
    disp::Ptr windows = disp::GetObject(hwp, L"XHwpWindows");
    disp::Ptr window = windows ? disp::GetObject(windows.get(), L"Active_XHwpWindow") : disp::Ptr();
    disp::Ptr layout = window ? disp::GetObject(window.get(), L"XHwpToolbarLayout") : disp::Ptr();
    Trace(L"toolbar: layout", layout ? L"ok" : L"none");
    if (!layout) return 0;
    disp::CallString(layout.get(), L"ChangeSerializePath", kSerializePath);
    bool fresh = disp::GetBool(layout.get(), L"IsNewSerializePath", false);
    Trace(L"toolbar: IsNewSerializePath", fresh ? L"true" : L"false");
    if (!fresh || g_toolbarCreated) return 1;  // already added
    g_toolbarCreated = true;
    disp::Ptr bar = disp::CallObject(layout.get(), L"CreateToolbar", L"C2PA", nullptr, 0);
    Trace(L"toolbar: CreateToolbar", bar ? L"ok" : L"none");
    if (!bar) return 0;
    const std::wstring saveId = L"HwpxC2paSaveSign", verifyId = L"HwpxC2paVerify";
    disp::Ptr b1 = disp::CallObject(layout.get(), L"CreateToolbarButton",
                                    L"C2PA 저장", &saveId, 0);
    disp::Ptr b2 = disp::CallObject(layout.get(), L"CreateToolbarButton",
                                    L"C2PA 출처", &verifyId, 0);
    Trace(L"toolbar: buttons", (b1 && b2) ? L"ok" : L"missing");
    for (disp::Ptr* b : {&b1, &b2}) {
        if (!*b) continue;
        disp::CallLongLong(b->get(), L"ModifyStyle", 0, 3);  // image and text
        disp::CallObjectLong(bar.get(), L"InsertToolbarButton", b->get(), -1);
    }
    return 1;
}

class Module : public IHncUserActionModule {
public:
    LPCSTR EnumAction(int i) override {
        Trace(L"EnumAction", i == 0 ? L"0" : L"n");
        return (i >= 0 && i < (int)(sizeof(kActions) / sizeof(kActions[0]))) ? kActions[i] : nullptr;
    }
    BOOL GetActionImage(LPCSTR action, UINT, HBITMAP* bmp, int* index) override {
        int n = !action ? -1 : strcmp(action, kActions[0]) == 0 ? 0 : strcmp(action, kActions[1]) == 0 ? 1 : -1;
        HBITMAP strip = n < 0 ? nullptr : ButtonStrip();
        if (bmp) *bmp = strip;
        if (index) *index = n < 0 ? 0 : n;
        return strip != nullptr;
    }
    BOOL UpdateUI(LPCSTR, LPDISPATCH, UINT* state) override {
        if (state) *state = 0;
        return TRUE;
    }
    int DoAction(LPCSTR action, LPDISPATCH hwp) override {
        Trace(L"DoAction", action ? std::wstring(action, action + strlen(action)).c_str() : L"(null)");
        if (!action || !hwp) return 0;
        if (strcmp(action, kActions[0]) == 0) return SaveAndSign(hwp, false);
        if (strcmp(action, kActions[3]) == 0) return SaveAndSign(hwp, true);
        if (strcmp(action, kActions[1]) == 0) return Verify(hwp);
        if (strcmp(action, kActions[2]) == 0) return InstallToolbar(hwp);
        // Load events sent by Hangul: put the toolbar in place (once per layout name).
        if (_stricmp(action, HNC_USERACTION_ON_INITIAL_LOAD) == 0 ||
            _stricmp(action, HNC_USERACTION_ON_LOAD) == 0) {
            ReplaceSave(hwp);
            return InstallToolbar(hwp);
        }
        return 0;
    }
};

Module g_module;

}  // namespace

// Exported through HwpxC2paAddon.def.
extern "C" IHncUserActionModule* __stdcall QueryUserActionInterface() {
    Trace(L"QueryUserActionInterface");
    return &g_module;
}

BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) Trace(L"DllMain attach");
    return TRUE;
}
