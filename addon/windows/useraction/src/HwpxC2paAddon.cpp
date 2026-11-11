// hwpx-c2pa add-on for Hangul (Windows): a User Action Module.
//
// STATUS: experimental. Builds in CI (MSVC, Win32); NOT YET TESTED IN HANGUL. Written against
// Hancom's "Addon Action" guide (2008) and the HWP Automation manual (2504).
//
// Actions
//   HwpxC2paSaveSign : save the active document, then embed Content Credentials
//                      (the version on disk before the save becomes parentOf)
//   HwpxC2paVerify   : validate the Content Credentials of the active document
//   HwpxC2paToolbar  : add a toolbar with the two buttons above
//
// The C2PA work is done by the hwpx-c2pa command line tool (Python), started as
// a child process, so this DLL has no C2PA or Python dependency of its own.
// The tool is looked up in HKCU\Software\hwpx-c2pa\Cli (REG_SZ), else on PATH.
//
// Copyright (c) 2026 Dongsun Nam (speeno). MIT License.
#include <windows.h>
#include <tchar.h>
#include <string>

#include "Dispatch.h"
#include "HncUserAction.h"

namespace {

const TCHAR* kActions[] = {_T("HwpxC2paSaveSign"), _T("HwpxC2paVerify"), _T("HwpxC2paToolbar")};
const wchar_t* kSerializePath = L"hwpx-c2pa\\toolbar_v1";

std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), &w[0], n);
    return w;
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

    // IXHwpDocument.Save(save_if_dirty): asks for a name if the document has none.
    disp::CallBool(doc.get(), L"Save", false);
    std::wstring path = disp::GetString(doc.get(), L"FullName");
    int result = 0;
    if (!IsHwpx(path)) {
        Notify(L"HWPX 형식으로 저장된 문서만 서명합니다.\nOnly documents saved as HWPX are signed.",
               MB_ICONWARNING);
    } else {
        std::wstring args = L"sign " + Quote(path);
        if (!parentCopy.empty()) args += L" --parent " + Quote(parentCopy);
        std::wstring out;
        int code = RunCli(args, &out);
        if (code == -1) Notify(kCliMissing, MB_ICONERROR);
        else if (code != 0) Notify(L"C2PA 서명 실패 / signing failed\n\n" + out, MB_ICONERROR);
        else if (out.find(L"locked") != std::wstring::npos)
            // Hangul keeps the saved file locked; the tool wrote <name>.c2pa.hwpx instead.
            Notify(L"문서가 잠겨 있어 서명본을 별도 파일로 저장했습니다.\n"
                   L"The document is locked; the signed copy was written separately.\n\n" + out);
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
    if (!layout) return 0;
    disp::CallString(layout.get(), L"ChangeSerializePath", kSerializePath);
    if (!disp::GetBool(layout.get(), L"IsNewSerializePath", false)) return 1;  // already added
    disp::Ptr bar = disp::CallObject(layout.get(), L"CreateToolbar", L"C2PA", nullptr, 0);
    if (!bar) return 0;
    const std::wstring saveId = L"HwpxC2paSaveSign", verifyId = L"HwpxC2paVerify";
    disp::Ptr b1 = disp::CallObject(layout.get(), L"CreateToolbarButton",
                                    L"C2PA 서명 저장 (Save && Sign)", &saveId, 0);
    disp::Ptr b2 = disp::CallObject(layout.get(), L"CreateToolbarButton",
                                    L"C2PA 검증 (Verify)", &verifyId, 0);
    for (disp::Ptr* b : {&b1, &b2}) {
        if (!*b) continue;
        disp::CallLongLong(b->get(), L"ModifyStyle", 2, 1);  // text only: no image supplied
        disp::CallObjectLong(bar.get(), L"InsertToolbarButton", b->get(), -1);
    }
    return 1;
}

class Module : public IHncUserActionModule {
public:
    LPCTSTR EnumAction(int i) override {
        return (i >= 0 && i < (int)(sizeof(kActions) / sizeof(kActions[0]))) ? kActions[i] : nullptr;
    }
    BOOL GetActionImage(LPCTSTR, UINT, HBITMAP* bmp, int* index) override {
        if (bmp) *bmp = nullptr;  // text-only buttons
        if (index) *index = 0;
        return FALSE;
    }
    BOOL UpdateUI(LPCTSTR, LPDISPATCH, UINT* state) override {
        if (state) *state = 0;
        return TRUE;
    }
    int DoAction(LPCTSTR action, LPDISPATCH hwp) override {
        if (!action || !hwp) return 0;
        if (_tcscmp(action, kActions[0]) == 0) return SaveAndSign(hwp);
        if (_tcscmp(action, kActions[1]) == 0) return Verify(hwp);
        if (_tcscmp(action, kActions[2]) == 0) return InstallToolbar(hwp);
        return 0;
    }
};

Module g_module;

}  // namespace

// Exported through HwpxC2paAddon.def.
extern "C" IHncUserActionModule* __stdcall QueryUserActionInterface() {
    return &g_module;
}
