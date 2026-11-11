#include "Dispatch.h"

namespace disp {

Ptr::Ptr(IDispatch* p, bool addRef) : p_(p) {
    if (p_ && addRef) p_->AddRef();
}
Ptr::Ptr(const Ptr& o) : p_(o.p_) {
    if (p_) p_->AddRef();
}
Ptr& Ptr::operator=(const Ptr& o) {
    if (this != &o) {
        if (o.p_) o.p_->AddRef();
        if (p_) p_->Release();
        p_ = o.p_;
    }
    return *this;
}
Ptr::~Ptr() {
    if (p_) p_->Release();
}

HRESULT Invoke(IDispatch* obj, const wchar_t* name, WORD flags, VARIANT* argsReversed,
               UINT argCount, VARIANT* result) {
    if (!obj) return E_POINTER;
    DISPID id = 0;
    LPOLESTR n = const_cast<LPOLESTR>(name);
    HRESULT hr = obj->GetIDsOfNames(IID_NULL, &n, 1, LOCALE_USER_DEFAULT, &id);
    if (FAILED(hr)) return hr;
    DISPPARAMS dp = {argsReversed, nullptr, argCount, 0};
    DISPID putId = DISPID_PROPERTYPUT;
    if (flags & DISPATCH_PROPERTYPUT) {
        dp.rgdispidNamedArgs = &putId;
        dp.cNamedArgs = 1;
    }
    return obj->Invoke(id, IID_NULL, LOCALE_USER_DEFAULT, flags, &dp, result, nullptr, nullptr);
}

Ptr GetObject(IDispatch* obj, const wchar_t* property) {
    VARIANT v;
    VariantInit(&v);
    if (FAILED(Invoke(obj, property, DISPATCH_PROPERTYGET, nullptr, 0, &v))) return Ptr();
    if (v.vt != VT_DISPATCH || !v.pdispVal) {
        VariantClear(&v);
        return Ptr();
    }
    return Ptr(v.pdispVal, false);  // takes the reference held by the VARIANT
}

std::wstring GetString(IDispatch* obj, const wchar_t* property) {
    VARIANT v;
    VariantInit(&v);
    std::wstring out;
    if (SUCCEEDED(Invoke(obj, property, DISPATCH_PROPERTYGET, nullptr, 0, &v)) &&
        SUCCEEDED(VariantChangeType(&v, &v, 0, VT_BSTR)) && v.bstrVal) {
        out.assign(v.bstrVal, SysStringLen(v.bstrVal));
    }
    VariantClear(&v);
    return out;
}

bool GetBool(IDispatch* obj, const wchar_t* property, bool fallback) {
    VARIANT v;
    VariantInit(&v);
    bool out = fallback;
    if (SUCCEEDED(Invoke(obj, property, DISPATCH_PROPERTYGET | DISPATCH_METHOD, nullptr, 0, &v)) &&
        SUCCEEDED(VariantChangeType(&v, &v, 0, VT_BOOL))) {
        out = v.boolVal != VARIANT_FALSE;
    }
    VariantClear(&v);
    return out;
}

bool PutString(IDispatch* obj, const wchar_t* property, const std::wstring& value) {
    VARIANT v;
    VariantInit(&v);
    v.vt = VT_BSTR;
    v.bstrVal = SysAllocStringLen(value.data(), static_cast<UINT>(value.size()));
    HRESULT hr = Invoke(obj, property, DISPATCH_PROPERTYPUT, &v, 1, nullptr);
    VariantClear(&v);
    return SUCCEEDED(hr);
}

bool PutLong(IDispatch* obj, const wchar_t* property, long value) {
    VARIANT v;
    VariantInit(&v);
    v.vt = VT_I4;
    v.lVal = value;
    return SUCCEEDED(Invoke(obj, property, DISPATCH_PROPERTYPUT, &v, 1, nullptr));
}

bool Call(IDispatch* obj, const wchar_t* method) {
    VARIANT r;
    VariantInit(&r);
    HRESULT hr = Invoke(obj, method, DISPATCH_METHOD, nullptr, 0, &r);
    VariantClear(&r);
    return SUCCEEDED(hr);
}

bool CallBool(IDispatch* obj, const wchar_t* method, bool arg) {
    VARIANT a, r;
    VariantInit(&a);
    VariantInit(&r);
    a.vt = VT_BOOL;
    a.boolVal = arg ? VARIANT_TRUE : VARIANT_FALSE;
    HRESULT hr = Invoke(obj, method, DISPATCH_METHOD, &a, 1, &r);
    VariantClear(&r);
    return SUCCEEDED(hr);
}

bool CallString(IDispatch* obj, const wchar_t* method, const std::wstring& arg) {
    VARIANT a, r;
    VariantInit(&a);
    VariantInit(&r);
    a.vt = VT_BSTR;
    a.bstrVal = SysAllocStringLen(arg.data(), static_cast<UINT>(arg.size()));
    HRESULT hr = Invoke(obj, method, DISPATCH_METHOD, &a, 1, &r);
    VariantClear(&a);
    VariantClear(&r);
    return SUCCEEDED(hr);
}

Ptr CallObject(IDispatch* obj, const wchar_t* method, const std::wstring& s1,
               const std::wstring* s2, long n) {
    VARIANT args[3];
    for (auto& a : args) VariantInit(&a);
    UINT count = 0;
    // DISPPARAMS take the arguments in reverse order.
    args[count].vt = VT_I4;
    args[count++].lVal = n;
    if (s2) {
        args[count].vt = VT_BSTR;
        args[count++].bstrVal = SysAllocStringLen(s2->data(), static_cast<UINT>(s2->size()));
    }
    args[count].vt = VT_BSTR;
    args[count++].bstrVal = SysAllocStringLen(s1.data(), static_cast<UINT>(s1.size()));
    VARIANT r;
    VariantInit(&r);
    HRESULT hr = Invoke(obj, method, DISPATCH_METHOD, args, count, &r);
    for (UINT i = 0; i < count; ++i) VariantClear(&args[i]);
    if (FAILED(hr) || r.vt != VT_DISPATCH || !r.pdispVal) {
        VariantClear(&r);
        return Ptr();
    }
    return Ptr(r.pdispVal, false);
}

bool CallObjectLong(IDispatch* obj, const wchar_t* method, IDispatch* arg, long n) {
    VARIANT args[2], r;
    VariantInit(&args[0]);
    VariantInit(&args[1]);
    VariantInit(&r);
    args[0].vt = VT_I4;
    args[0].lVal = n;
    args[1].vt = VT_DISPATCH;
    args[1].pdispVal = arg;  // borrowed; not cleared below
    HRESULT hr = Invoke(obj, method, DISPATCH_METHOD, args, 2, &r);
    VariantClear(&r);
    return SUCCEEDED(hr);
}

bool CallLongLong(IDispatch* obj, const wchar_t* method, long a, long b) {
    VARIANT args[2], r;
    VariantInit(&args[0]);
    VariantInit(&args[1]);
    VariantInit(&r);
    args[0].vt = VT_I4;
    args[0].lVal = b;
    args[1].vt = VT_I4;
    args[1].lVal = a;
    HRESULT hr = Invoke(obj, method, DISPATCH_METHOD, args, 2, &r);
    VariantClear(&r);
    return SUCCEEDED(hr);
}

}  // namespace disp
