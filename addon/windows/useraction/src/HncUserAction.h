// Hangul "User Action Module" interface.
//
// Re-declared from Hancom's published guide "Event Handler 추가하기 - 한글 Addon
// Action" (version 1.0, external distribution, 2008-08-04). A module is a DLL
// registered under HKEY_CURRENT_USER\Software\Hnc\HwpUserAction\Modules that
// exports QueryUserActionInterface(); Hangul enumerates its actions and calls
// DoAction() with the IHwpObject automation object.
#pragma once

#include <windows.h>
#include <oaidl.h>

struct IHncUserActionModule {
    // Called with 0, 1, 2, ... until it returns NULL; returns the action names.
    virtual LPCTSTR EnumAction(int nIterator) = 0;
    // Toolbar image: a 32-bit BMP strip of 16x16 buttons (60 per row).
    virtual BOOL GetActionImage(LPCTSTR szAction, UINT uState, HBITMAP* lphBitmap,
                                int* lpnImageIndex) = 0;
    // UI state: 0, DFCS_INACTIVE, DFCS_CHECKED or DFCS_BUTTON3STATE.
    virtual BOOL UpdateUI(LPCTSTR szAction, LPDISPATCH pObject /* IHwpObject */,
                          UINT* lpuState) = 0;
    // Runs the action.
    virtual int DoAction(LPCTSTR szAction, LPDISPATCH pObject /* IHwpObject */) = 0;
};

extern "C" IHncUserActionModule* __stdcall QueryUserActionInterface();
