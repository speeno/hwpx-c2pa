// Minimal late binding over IDispatch, so the add-on needs no Hancom headers or
// type libraries. Names follow the HWP Automation manual (HwpAutomation_2504).
#pragma once

#include <windows.h>
#include <oaidl.h>
#include <string>

namespace disp {

// Owning IDispatch pointer.
class Ptr {
public:
    Ptr() = default;
    explicit Ptr(IDispatch* p, bool addRef);
    Ptr(const Ptr& o);
    Ptr& operator=(const Ptr& o);
    ~Ptr();
    IDispatch* get() const { return p_; }
    explicit operator bool() const { return p_ != nullptr; }

private:
    IDispatch* p_ = nullptr;
};

HRESULT Invoke(IDispatch* obj, const wchar_t* name, WORD flags, VARIANT* argsReversed,
               UINT argCount, VARIANT* result);

Ptr GetObject(IDispatch* obj, const wchar_t* property);
std::wstring GetString(IDispatch* obj, const wchar_t* property);
bool GetBool(IDispatch* obj, const wchar_t* property, bool fallback);
bool PutString(IDispatch* obj, const wchar_t* property, const std::wstring& value);
bool PutLong(IDispatch* obj, const wchar_t* property, long value);

// Method calls with simple argument lists (arguments in natural order).
bool Call(IDispatch* obj, const wchar_t* method);
bool CallBool(IDispatch* obj, const wchar_t* method, bool arg);
bool CallString(IDispatch* obj, const wchar_t* method, const std::wstring& arg);
Ptr CallObject(IDispatch* obj, const wchar_t* method, const std::wstring& s1,
               const std::wstring* s2, long n);
bool CallObjectLong(IDispatch* obj, const wchar_t* method, IDispatch* arg, long n);
bool CallLongLong(IDispatch* obj, const wchar_t* method, long a, long b);

}  // namespace disp
