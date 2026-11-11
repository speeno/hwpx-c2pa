// Hangul "User Action Module" interface.
//
// Re-declared from Hancom's published guide "Event Handler 추가하기 - 한글 Addon
// Action" (version 1.0, external distribution, 2008-08-04). A module is a DLL
// registered under HKEY_CURRENT_USER\Software\Hnc\HwpUserAction\Modules that
// exports QueryUserActionInterface(); Hangul enumerates its actions and calls
// DoAction() with the IHwpObject automation object.
//
// Found in the first test with Hangul 2024 (13.0.0.4226): the strings of this
// interface are ANSI (char*), whatever the module is built as, and Hangul also
// calls DoAction() with two GUID strings: once when the module is first used
// (OnInitialLoad in the guide) and each time a window loads it (OnLoad).
#pragma once

#include <windows.h>
#include <oaidl.h>

struct IHncUserActionModule {
    // Called with 0, 1, 2, ... until it returns NULL; returns the action names.
    virtual LPCSTR EnumAction(int nIterator) = 0;
    // Toolbar image: a 32-bit BMP strip of 16x16 buttons (60 per row).
    virtual BOOL GetActionImage(LPCSTR szAction, UINT uState, HBITMAP* lphBitmap,
                                int* lpnImageIndex) = 0;
    // UI state: 0, DFCS_INACTIVE, DFCS_CHECKED or DFCS_BUTTON3STATE.
    virtual BOOL UpdateUI(LPCSTR szAction, LPDISPATCH pObject /* IHwpObject */,
                          UINT* lpuState) = 0;
    // Runs the action.
    virtual int DoAction(LPCSTR szAction, LPDISPATCH pObject /* IHwpObject */) = 0;
};

// Passed to DoAction() by Hangul itself (observed in that order after RegisterModule).
#define HNC_USERACTION_ON_INITIAL_LOAD "{B91A2981-A001-44a9-933F-5BF70A747967}"
#define HNC_USERACTION_ON_LOAD "{3E4DC866-051C-4989-820E-DADC1E6264B9}"

extern "C" IHncUserActionModule* __stdcall QueryUserActionInterface();
