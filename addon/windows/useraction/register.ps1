# Register (or remove) the hwpx-c2pa add-on for the current user. NOT YET TESTED.
#   .\register.ps1 -Dll C:\path\HwpxC2paAddon.dll [-Cli C:\path\hwpx-c2pa.exe]
#   .\register.ps1 -Remove
param([string]$Dll, [string]$Cli, [switch]$Remove)

$modules = "HKCU:\Software\Hnc\HwpUserAction\Modules"
$own = "HKCU:\Software\hwpx-c2pa"
if ($Remove) {
    Remove-ItemProperty -Path $modules -Name "HwpxC2pa" -ErrorAction SilentlyContinue
    Remove-Item -Path $own -Recurse -ErrorAction SilentlyContinue
    Write-Host "removed"; exit 0
}
if (-not $Dll -or -not (Test-Path $Dll)) { Write-Error "give -Dll <path to HwpxC2paAddon.dll>"; exit 1 }
New-Item -Path $modules -Force | Out-Null
Set-ItemProperty -Path $modules -Name "HwpxC2pa" -Value (Resolve-Path $Dll).Path
if (-not $Cli) { $Cli = (Get-Command hwpx-c2pa.exe -ErrorAction SilentlyContinue).Source }
if ($Cli) {
    New-Item -Path $own -Force | Out-Null
    Set-ItemProperty -Path $own -Name "Cli" -Value $Cli
}
Write-Host "registered. Restart Hangul. / 등록했습니다. 한글을 다시 시작하십시오."
