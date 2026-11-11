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
#include <initializer_list>
#include <string>

#include "Dispatch.h"
#include "HncUserAction.h"

namespace {

const char* kActions[] = {"HwpxC2paSaveSign", "HwpxC2paVerify", "HwpxC2paToolbar"};
const wchar_t* kSerializePath = L"hwpx-c2pa\\toolbar_v2";
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
    bool ok = CallStrings(hwp, L"ReplaceAction", {L"FileSave", L"HwpxC2paSaveSign"});
    Trace(L"ReplaceAction FileSave", ok ? L"ok" : L"failed");
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

int SaveAndSign(IDispatch* hwp) {
    disp::Ptr doc = ActiveDocument(hwp);
    if (!doc) return 0;

    // Keep the version on disk before the save; it becomes the parent if it is intact.
    std::wstring before = disp::GetString(doc.get(), L"FullName");
    std::wstring parentCopy;
    if (IsHwpx(before) && GetFileAttributesW(before.c_str()) != INVALID_FILE_ATTRIBUTES) {
        wchar_t tmpDir[MAX_PATH], tmp[MAX_PATH];
        GetTempPathW(MAX_PATH, tmpDir);
        if (GetTempFileNameW(tmpDir, L"c2p", 0, tmp) && CopyFileW(before.c_str(), tmp, FALSE)) {
            if (RunCli(L"verify " + Quote(tmp), nullptr) == 0) parentCopy = tmp;
            else DeleteFileW(tmp);
        }
    }

    // Save without keeping the file locked ("lock:false"), so the record can go into
    // the very file the user has open. A document without a name, or in another
    // format, goes through Hangul's own save first (it asks for a name).
    bool saved;
    if (IsHwpx(before)) {
        saved = CallStrings(hwp, L"SaveAs", {before.c_str(), L"HWPX", L"lock:false"});
        Trace(L"SaveAs lock:false", saved ? L"ok" : L"failed");
        if (!saved) saved = RunBuiltIn(hwp, L"FileSave");
    } else {
        saved = RunBuiltIn(hwp, L"FileSave");
        Trace(L"built-in FileSave", saved ? L"ok" : L"failed");
    }
    doc = ActiveDocument(hwp);
    std::wstring path = doc ? disp::GetString(doc.get(), L"FullName") : L"";
    int result = 0;
    if (!IsHwpx(path)) {
        result = saved ? 1 : 0;  // not an HWPX document: saved as usual, nothing to record
    } else {
        if (!IsHwpx(before)) {  // first save of a new document: write once more without the lock
            bool again = CallStrings(hwp, L"SaveAs", {path.c_str(), L"HWPX", L"lock:false"});
            Trace(L"SaveAs lock:false (new document)", again ? L"ok" : L"failed");
        }
        std::wstring args = L"sign " + Quote(path);
        if (!parentCopy.empty()) args += L" --parent " + Quote(parentCopy);
        std::wstring out;
        int code = RunCli(args, &out);
        Trace(L"sign exit", std::to_wstring(code).c_str());
        if (code == -1) Notify(kCliMissing, MB_ICONERROR);
        else if (code != 0) Notify(L"C2PA 기록 실패 / recording failed\n\n" + out, MB_ICONERROR);
        else if (out.find(L"locked") != std::wstring::npos)
            // Hangul still holds the file; the tool wrote <name>.c2pa.hwpx instead.
            SwapInRecordedCopy(hwp, doc.get(), path);
        result = code == 0 ? 1 : 0;
    }
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
    std::wstring out;
    int code = RunCli(L"verify " + Quote(path), &out);
    if (code == -1) {
        Notify(kCliMissing, MB_ICONERROR);
        return 0;
    }
    // 0 intact, 1 invalid, 2 no credentials, 3+ error
    Notify(out, code == 0 ? MB_ICONINFORMATION : (code == 2 ? MB_ICONWARNING : MB_ICONERROR));
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
                                    L"C2PA 기록 저장 (Save && Record)", &saveId, 0);
    disp::Ptr b2 = disp::CallObject(layout.get(), L"CreateToolbarButton",
                                    L"C2PA 출처 확인 (Provenance)", &verifyId, 0);
    Trace(L"toolbar: buttons", (b1 && b2) ? L"ok" : L"missing");
    for (disp::Ptr* b : {&b1, &b2}) {
        if (!*b) continue;
        disp::CallLongLong(b->get(), L"ModifyStyle", 2, 1);  // text only: no image supplied
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
    BOOL GetActionImage(LPCSTR, UINT, HBITMAP* bmp, int* index) override {
        if (bmp) *bmp = nullptr;  // text-only buttons
        if (index) *index = 0;
        return FALSE;
    }
    BOOL UpdateUI(LPCSTR, LPDISPATCH, UINT* state) override {
        if (state) *state = 0;
        return TRUE;
    }
    int DoAction(LPCSTR action, LPDISPATCH hwp) override {
        Trace(L"DoAction", action ? std::wstring(action, action + strlen(action)).c_str() : L"(null)");
        if (!action || !hwp) return 0;
        if (strcmp(action, kActions[0]) == 0) return SaveAndSign(hwp);
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
