cmake_minimum_required(VERSION 3.20)
project(HwpxC2paAddon LANGUAGES CXX)

# Build for the same bitness as Hwp.exe (32-bit for Hangul 2022 and earlier):
#   cmake -A Win32 -B build && cmake --build build --config Release
# Static C runtime: the DLL must load in Hangul without a separate VC++ redistributable.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_definitions(-DUNICODE -D_UNICODE)
if(MSVC)
  add_compile_options(/utf-8)  # the sources hold Korean text in UTF-8
endif()

add_library(HwpxC2paAddon SHARED src/HwpxC2paAddon.cpp src/Dispatch.cpp src/HwpxC2paAddon.def)
target_link_libraries(HwpxC2paAddon PRIVATE oleaut32 ole32 advapi32 user32)
