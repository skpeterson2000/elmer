# ELMER installer for Windows.
#
# The Linux installer's job is mostly deciding between apt and a virtual
# environment, because the system Python on a Pi is externally managed and pip
# will refuse it. Windows has no such argument: there is no system Python to
# protect, so this always builds a virtual environment in .venv and installs
# the three dependencies into it.
#
# What it will not do is pretend. The kiosk is a Linux appliance and is not
# ported; poppler is not on a Windows machine by default and the one feature
# that needs it says so rather than failing later. Both are printed at the end
# rather than left to be discovered.
#
#     powershell -ExecutionPolicy Bypass -File install.ps1
#
# The execution policy on a Windows client defaults to Restricted, which is
# why that first part is not optional. It applies to this one command and
# changes nothing about the machine.

[CmdletBinding()]
param(
    [switch]$Shortcut,      # put ELMER on the Start Menu
    [switch]$Serial,        # add pyserial, for the NanoVNA in the Lab
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Ok   ($m) { Write-Host "  [ ok ]  $m"  -ForegroundColor Green }
function Miss ($m) { Write-Host "  [miss]  $m"  -ForegroundColor Yellow }
function Warn ($m) { Write-Host "  [warn]  $m"  -ForegroundColor Yellow }
function Bad  ($m) { Write-Host "  [FAIL]  $m"  -ForegroundColor Red }

if ($Help) {
    Write-Host @"

  ELMER on Windows

    powershell -ExecutionPolicy Bypass -File install.ps1
    ... -Shortcut     also put ELMER on the Start Menu
    ... -Serial       also install pyserial, for the NanoVNA in the Lab

  Afterwards, start it with elmer.cmd - or with .venv\Scripts\python.exe elmer.py

"@
    exit 0
}

Write-Host ""
Write-Host "  ELMER - Windows install" -ForegroundColor Cyan
Write-Host "  $root"
Write-Host ""

# ---------------------------------------------------------------- python
# The py launcher is the reliable way to find a real Python on Windows:
# "python" on PATH is often the Microsoft Store stub, which is not one.
$py = $null
foreach ($try in @(@('py', '-3'), @('python'), @('python3'))) {
    $exe = Get-Command $try[0] -ErrorAction SilentlyContinue
    if (-not $exe) { continue }
    $args = @()
    if ($try.Count -gt 1) { $args = $try[1..($try.Count - 1)] }
    try {
        $v = & $exe.Source @args -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    } catch { continue }
    if ($LASTEXITCODE -eq 0 -and $v) {
        $py = @{ Exe = $exe.Source; Args = $args; Version = $v.Trim() }
        break
    }
}

if (-not $py) {
    Bad "no Python found. Install it from python.org or the Microsoft Store,"
    Write-Host "          tick 'Add python.exe to PATH', and run this again."
    exit 1
}

$parts = $py.Version.Split('.')
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 9)) {
    Bad "python $($py.Version) is too old; ELMER needs 3.9 or newer"
    exit 1
}
Ok "python $($py.Version)"

# ------------------------------------------------------------------ venv
$venv = Join-Path $root '.venv'
$vpy  = Join-Path $venv 'Scripts\python.exe'

if (Test-Path $vpy) {
    Ok "using the virtual environment already at .venv"
} else {
    Miss "no virtual environment yet - making one at .venv"
    & $py.Exe @($py.Args) -m venv $venv
    if (-not (Test-Path $vpy)) { Bad "could not create .venv"; exit 1 }
    Ok "virtual environment created"
}

# --------------------------------------------------------------- packages
Write-Host ""
Write-Host "  Installing Flask, Pillow and reportlab into .venv ..."
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Bad "pip could not install the dependencies"; exit 1 }
Ok "python packages installed"

if ($Serial) {
    & $vpy -m pip install --quiet pyserial
    if ($LASTEXITCODE -eq 0) { Ok "pyserial installed - the Lab can talk to a NanoVNA" }
    else { Warn "pyserial would not install; the VNA panel will say so" }
}

# --------------------------------------------------------------- shortcut
if ($Shortcut) {
    try {
        $lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'ELMER.lnk'
        $sh = New-Object -ComObject WScript.Shell
        $s = $sh.CreateShortcut($lnk)
        $s.TargetPath = Join-Path $root 'elmer.cmd'
        $s.WorkingDirectory = $root
        $s.Description = 'ELMER - radio study and propagation'
        $s.Save()
        Ok "Start Menu shortcut written"
    } catch {
        Warn "could not write the Start Menu shortcut: $($_.Exception.Message)"
    }
}

# ------------------------------------------------- what is not here, said
Write-Host ""
if (Get-Command pdftotext -ErrorAction SilentlyContinue) {
    Ok "poppler found - the NIFOG reader will work"
} else {
    Miss "poppler is not installed, so the NIFOG channel reader cannot read"
    Write-Host "          its PDF. Everything else works. Install poppler and"
    Write-Host "          put pdftotext on PATH if you want that page."
}
Miss "the full-screen kiosk is Linux-only and is not installed here"

Write-Host ""
Write-Host "  Start ELMER with:" -ForegroundColor Cyan
Write-Host "      .\elmer.cmd"
Write-Host "  then open http://localhost:5000"
Write-Host ""
