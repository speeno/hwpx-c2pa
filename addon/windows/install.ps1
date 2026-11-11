# Install hwpx-c2pa and its Hangul add-in for the current user (Windows).
#
#   powershell -ExecutionPolicy Bypass -File addon\windows\install.ps1 [-Dll path\HwpxC2paAddon.dll] [-NoTestCerts]
#
# Steps: Python 3.12 x64 (only if missing), a private virtual environment with the
# engine, the C2PA native library, test certificates + settings (unless -NoTestCerts),
# the add-in DLL matching the bitness of Hwp.exe, registry entries under HKCU, and a
# desktop shortcut "Hangul C2PA" that starts Hangul with the add-in loaded.
# No administrator rights are needed. Remove with: addon\windows\useraction\register.ps1 -Remove
#
# Copyright (c) 2026 Dongsun Nam (speeno). MIT License.
param([string]$Dll, [switch]$NoTestCerts)
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$release = "https://github.com/speeno/hwpx-c2pa/releases/download/v0.1.0"
$base = Join-Path $env:LOCALAPPDATA "hwpx-c2pa"
New-Item -ItemType Directory -Force -Path $base | Out-Null
$log = Join-Path $base "setup-log.txt"
"hwpx-c2pa install $(Get-Date -Format s) user=$env:USERNAME arch=$env:PROCESSOR_ARCHITECTURE" | Set-Content $log
function Say($t, $c = "Cyan") { Write-Host $t -ForegroundColor $c; Add-Content $log $t }
function Step($name, $block) {
    Say "== $name"
    try { & $block 2>&1 | ForEach-Object { Add-Content $log "$_"; Write-Host "   $_" }; Say "   ok" "Green" }
    catch { Say "   FAILED: $($_.Exception.Message)" "Red" }
}
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$py = $null
Step "Python (x64)" {
    $cands = @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")
    $found = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $found) {
        $inst = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
        Invoke-WebRequest "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile $inst -UseBasicParsing
        Start-Process $inst -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0" -Wait
        $found = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $found) { throw "Python was not installed" }
    $script:py = $found
    & $found --version
}
$venv = Join-Path $base "venv"
$cli = Join-Path $venv "Scripts\hwpx-c2pa.exe"
Step "hwpx-c2pa engine" {
    $src = $repo
    if (-not (Test-Path "$venv\Scripts\python.exe")) { & $script:py -m venv $venv }
    & "$venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    & "$venv\Scripts\python.exe" -m pip install --quiet "${src}[devcerts,windows]"
    if (-not (Test-Path $cli)) { throw "hwpx-c2pa.exe missing" }
    & $cli --version
}
Step "C2PA native library (fetch-lib)" { & $cli fetch-lib; & $cli info }
if (-not $NoTestCerts) { Step "Test certificates and settings (replace with your own certificate for real use)" {
    $certs = Join-Path $base "certs"
    if (-not (Test-Path "$certs\signer.key")) { & $cli dev-certs $certs | Out-Null }
    $info = (& $cli info --json | Out-String | ConvertFrom-Json)
    $cfg = $info."config file"
    New-Item -ItemType Directory -Force -Path (Split-Path $cfg) | Out-Null
    $json = @{ cert = "$certs\signer-chain.pem"; key = "$certs\signer.key"; trust = "$certs\root-ca.pem" } | ConvertTo-Json
    [IO.File]::WriteAllText($cfg, $json, (New-Object Text.UTF8Encoding($false)))
    "config: $cfg"
} }
$hwp = $null
Step "Find Hangul (Hwp.exe)" {
    foreach ($k in "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Hwp.exe", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Hwp.exe") {
        $v = (Get-ItemProperty $k -ErrorAction SilentlyContinue)."(default)"
        if ($v -and (Test-Path $v)) { $script:hwp = $v; break }
    }
    if (-not $script:hwp) {
        $hit = Get-ChildItem "C:\Program Files\Hnc", "C:\Program Files (x86)\Hnc", "C:\Program Files\HNC", "C:\Program Files (x86)\HNC" -Recurse -Filter Hwp.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { $script:hwp = $hit.FullName }
    }
    if (-not $script:hwp) { throw "Hwp.exe not found" }
    $b = [IO.File]::ReadAllBytes($script:hwp)
    $pe = [BitConverter]::ToInt32($b, 0x3c); $m = [BitConverter]::ToUInt16($b, $pe + 4)
    $script:arch = if ($m -eq 0x8664) { "x64" } elseif ($m -eq 0x14c) { "Win32" } else { "unknown-$m" }
    "$($script:hwp)  version $((Get-Item $script:hwp).VersionInfo.FileVersion)  $($script:arch)"
}
Step "Hangul add-in (User Action module)" {
    if (-not $script:arch -or $script:arch -like "unknown*") { $script:arch = "Win32"; "bitness unknown, using Win32" }
    $dir = Join-Path $base "addon"; New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $dll = Join-Path $dir "HwpxC2paAddon.dll"
    if ($Dll) { Copy-Item $Dll $dll -Force }
    else { Invoke-WebRequest "$release/HwpxC2paAddon-$($script:arch).dll" -OutFile $dll -UseBasicParsing }
    New-Item -Path "HKCU:\Software\Hnc\HwpUserAction\Modules" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\Hnc\HwpUserAction\Modules" -Name "HwpxC2pa" -Value $dll
    New-Item -Path "HKCU:\Software\hwpx-c2pa" -Force | Out-Null
    Set-ItemProperty -Path "HKCU:\Software\hwpx-c2pa" -Name "Cli" -Value $cli
    "registered $dll ($($script:arch))"
}
Step "Samples and a first check" {
    $docs = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "hwpx-c2pa-samples"
    Copy-Item (Join-Path $repo "samples") $docs -Recurse -Force
    $env:PYTHONUTF8 = "1"
    & $cli history "$docs\en\3b-saved-in-hangul-resigned.hwpx"
    "samples: $docs"
}
Step "Desktop shortcut 'Hangul C2PA'" {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $sc = (New-Object -ComObject WScript.Shell).CreateShortcut("$desktop\Hangul C2PA.lnk")
    $sc.TargetPath = "$venv\Scripts\pythonw.exe"; $sc.Arguments = "-m hwpx_c2pa hangul"
    $sc.WorkingDirectory = [Environment]::GetFolderPath("MyDocuments")
    if ($script:hwp) { $sc.IconLocation = "$($script:hwp),0" }
    $sc.Save()
    "$desktop\Hangul C2PA.lnk"
}
Say "Done. Start Hangul with the 'Hangul C2PA' shortcut on the desktop. Log: $log" "Green"
