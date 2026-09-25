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
# What it will do is fetch what is missing, if asked. Python, git and poppler
# are each looked for; each one that is not here is named, with what it is
# for, and offered - and Windows has winget for exactly this, so the offer
# is one keypress rather than a website, a download and a wizard with a box
# to tick. Nothing is installed without the answer. -Yes answers for you;
# -NoInstall only reports, for a machine somebody else looks after.
#
#     powershell -ExecutionPolicy Bypass -File install.ps1
#
# The execution policy on a Windows client defaults to Restricted, which is
# why that first part is not optional. It applies to this one command and
# changes nothing about the machine. It runs from wherever this folder is -
# there is no path in it to edit.

[CmdletBinding()]
param(
    [switch]$Shortcut,      # put ELMER on the Start Menu
    [switch]$Serial,        # add pyserial, for the NanoVNA in the Lab
    [switch]$Yes,           # install whatever is missing without asking
    [switch]$NoInstall,     # only say what is missing; install nothing
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
    ... -Yes          install anything missing (Python, git, poppler) without asking
    ... -NoInstall    only say what is missing; install nothing

  Python, git and poppler are looked for. Each one missing is offered, and
  installed with winget only if you say so. Afterwards, start ELMER with
  elmer.cmd - or with .venv\Scripts\python.exe elmer.py

"@
    exit 0
}

Write-Host ""
Write-Host "  ELMER - Windows install" -ForegroundColor Cyan
Write-Host "  $root"
Write-Host ""

# Windows puts Desktop and Documents on OneDrive by default, so this is
# where a zip gets unzipped. Said once, not blocked: it works, but a venv is
# thousands of files for OneDrive to sync, and "files on demand" can later
# turn one of them into a cloud placeholder that Python cannot import. A
# folder off the sync - C:\ELMER, say - has neither problem.
if ($root -like '*OneDrive*') {
    Warn "this folder is inside OneDrive, so everything installed here is synced too."
    Write-Host "          It works, but a copy in a folder OneDrive does not sync - C:\ELMER, say -"
    Write-Host "          is faster to install and cannot be broken by a file going online-only."
}

# ------------------------------------------------ fetching what is missing
# winget is on every Windows 10 (21H2 and later) and Windows 11 machine. It is
# asked per package, and only ever after the person said yes - or said -Yes
# on the command line, which is the same thing said once.
$winget = Get-Command winget -ErrorAction SilentlyContinue
$interactive = -not [Console]::IsInputRedirected

function Update-SessionPath {
    # A fresh install writes PATH for new windows; this one is not new.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Request-Install ($what, $why, $id, $url) {
    # Say what is missing and what it is for; offer; install if told to.
    # Returns $true if it was installed.
    Miss "$what is not installed - $why"
    if ($NoInstall) {
        Write-Host "          (-NoInstall: not offered. Get it from $url)"
        return $false
    }
    if (-not $winget) {
        Write-Host "          winget is not on this machine, so it cannot be fetched from here."
        Write-Host "          Get it from $url and run this again."
        return $false
    }
    if (-not $Yes) {
        if (-not $interactive) {
            Write-Host "          (not asked - no keyboard here. Run with -Yes to install it.)"
            return $false
        }
        $answer = Read-Host "          Install $what now with winget? [Y/n]"
        if ($answer -and $answer.Trim().ToLower().StartsWith('n')) {
            Write-Host "          Left out. Get it from $url whenever you like."
            return $false
        }
    }
    Write-Host "          Installing $what ..."
    & $winget.Source install --id $id --exact --silent --accept-source-agreements --accept-package-agreements | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Warn "winget could not install $what (exit $LASTEXITCODE). Get it from $url"
        return $false
    }
    Update-SessionPath
    Ok "$what installed"
    return $true
}

# ---------------------------------------------------------------- python
# The py launcher is the reliable way to find a real Python on Windows:
# "python" on PATH is often the Microsoft Store stub, which is not one.
function Find-Python {
    foreach ($try in @(@('py', '-3'), @('python'), @('python3'))) {
        $exe = Get-Command $try[0] -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        $extra = @()
        if ($try.Count -gt 1) { $extra = $try[1..($try.Count - 1)] }
        try {
            $v = & $exe.Source @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $v) {
            return @{ Exe = $exe.Source; Args = $extra; Version = $v.Trim() }
        }
    }
    return $null
}

# A portable copy - the zip from a release - brings its own Python with the
# packages already in it, and pyserial too. There is nothing to build for
# it; what this script still does for one is git, poppler, and the connect
# step below that turns it into a copy that updates itself.
$portable = Join-Path $root 'python\python.exe'
if (Test-Path $portable) {
    $vpy = $portable
    $v = (& $vpy -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
    Ok "portable copy - python $v and the packages are bundled with it"
    if ($Serial) { Ok "pyserial is bundled too - the Lab can talk to a NanoVNA" }
} else {

$py = Find-Python
if (-not $py) {
    # python.org's build, with the py launcher that this script and elmer.cmd
    # both find it by. The Store's Python is real too, but its stub of the
    # same name is what "python" on a fresh machine usually is.
    if (Request-Install 'Python' 'ELMER is written in it' 'Python.Python.3.12' 'https://www.python.org/downloads/windows/') {
        $py = Find-Python
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

# TowerWitch beside ELMER: its Qt build is what the dashboard's TowerWitch
# button starts on Windows, and that wants PyQt5 in the same Python.
$tw = @((Join-Path $HOME 'TowerWitch'), (Join-Path (Split-Path $root -Parent) 'TowerWitch')) |
      Where-Object { Test-Path (Join-Path $_ 'TowerWitch-P.py') } | Select-Object -First 1
if ($tw) {
    $twReqs = Join-Path $tw 'requirements.txt'
    if (Test-Path $twReqs) { & $vpy -m pip install --quiet -r $twReqs }
    else { & $vpy -m pip install --quiet PyQt5 requests utm maidenhead mgrs packaging }
    if ($LASTEXITCODE -eq 0) { Ok "TowerWitch's packages installed - the dashboard's TowerWitch button can start $tw" }
    else { Warn "TowerWitch's packages would not install; the self-check offers a Fix for it" }
}

if ($Serial) {
    & $vpy -m pip install --quiet pyserial
    if ($LASTEXITCODE -eq 0) { Ok "pyserial installed - the Lab can talk to a NanoVNA" }
    else { Warn "pyserial would not install; the VNA panel will say so" }
}

}   # not portable

# ---------------------------------------------------------------- ELMER.exe
# The thing a person double-clicks, with the program's own icon on it. A
# .cmd cannot carry one; a small ELMER.exe that starts elmer.cmd beside it
# can, and every Windows has the C# compiler to build it with (it ships in
# the .NET Framework, under C:\Windows\Microsoft.NET). Source in
# tools\launcher\ELMER.cs; built here, not committed.
$exe = Join-Path $root 'ELMER.exe'
$csc = Join-Path ([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()) 'csc.exe'
if (Test-Path $csc) {
    & $csc /nologo /target:winexe /optimize+ "/out:$exe" "/win32icon:$(Join-Path $root 'elmer\static\elmer.ico')" `
        /reference:System.Windows.Forms.dll (Join-Path $root 'tools\launcher\ELMER.cs') | Out-Null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $exe)) { Ok "ELMER.exe built, with its icon - double-click that" }
    else { Warn "ELMER.exe would not build; elmer.cmd starts ELMER just the same" }
} else {
    Warn "no C# compiler at $csc; elmer.cmd starts ELMER just the same"
}

# --------------------------------------------------------------- shortcut
# ELMER on the Start Menu, with its own icon: the way a Windows program is
# found and started. Offered, like everything else; -Shortcut says yes
# without asking, and a shortcut already there is refreshed - it points at
# this folder, and a copy that moved would otherwise leave one pointing at
# nothing.
$lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'ELMER.lnk'
$wantShortcut = $Shortcut -or $Yes -or (Test-Path $lnk)
if (-not $wantShortcut -and -not $NoInstall -and $interactive) {
    $answer = Read-Host "  Put ELMER on the Start Menu, with its icon? [Y/n]"
    $wantShortcut = -not ($answer -and $answer.Trim().ToLower().StartsWith('n'))
}
if ($wantShortcut) {
    try {
        $sh = New-Object -ComObject WScript.Shell
        $s = $sh.CreateShortcut($lnk)
        $s.TargetPath = if (Test-Path $exe) { $exe } else { Join-Path $root 'elmer.cmd' }
        $s.WorkingDirectory = $root
        $s.Description = 'ELMER - radio study and propagation'
        $s.IconLocation = (Join-Path $root 'elmer\static\elmer.ico') + ',0'
        $s.WindowStyle = 7                 # the console minimized; the window is ELMER's
        $s.Save()
        Ok "ELMER is on the Start Menu, with its icon"
    } catch {
        Warn "could not write the Start Menu shortcut: $($_.Exception.Message)"
    }
}

# ------------------------------------------------- what is not here, said
# And offered. git is how ELMER updates itself; poppler is what reads the
# NIFOG channel PDF and the manuals on the shelf. Everything else works
# without either, so a "no" here is a working install with two things it
# will say are missing when they are asked for.
Write-Host ""
$haveGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if ($haveGit) {
    Ok "git found - ELMER can update itself"
} else {
    $haveGit = Request-Install 'git' 'ELMER updates itself with it' 'Git.Git' 'https://git-scm.com/download/win'
}

# The connect step. A copy that was unzipped or downloaded has no link back
# to where ELMER comes from, so it cannot update. With git here, one press
# gives it that link - the history is fetched alongside and nothing in the
# folder is overwritten - and from then on it updates like every other.
if ($haveGit -and -not (Test-Path (Join-Path $root '.git'))) {
    Miss "this copy is not connected to the repository, so it cannot update itself"
    $connect = $Yes
    if (-not $Yes -and -not $NoInstall -and $interactive) {
        $answer = Read-Host "          Connect it now? Nothing here is overwritten. [Y/n]"
        $connect = -not ($answer -and $answer.Trim().ToLower().StartsWith('n'))
    }
    if ($connect) {
        & $vpy (Join-Path $root 'elmer.py') --adopt
        if ($LASTEXITCODE -eq 0) { Ok "connected - Update now on the dashboard works from here on" }
        else { Warn "could not connect this copy; run .\elmer.cmd --adopt later to try again" }
    } else {
        Write-Host "          (run this again and say yes, or .\elmer.cmd --adopt, whenever you like)"
    }
}
if (Get-Command pdftotext -ErrorAction SilentlyContinue) {
    Ok "poppler found - the NIFOG reader and the library will work"
} else {
    $got = Request-Install 'poppler' 'it reads the NIFOG channel PDF and the manuals on the shelf' 'oschwartz10612.Poppler' 'https://github.com/oschwartz10612/poppler-windows/releases'
    if (-not $got) {
        Write-Host "          Everything else works. The NIFOG page and the library will say"
        Write-Host "          it is missing until it is here."
    }
}
Miss "the full-screen kiosk is Linux-only and is not installed here"

# The other copies. A machine collects them - a zip here, a clone there,
# OneDrive's Desktop - and a double-click lands on whichever one Explorer
# was showing. Listed, and the empty ones offered for removal, one question
# each; a copy with study or settings in it is named and left alone.
if ($interactive -and -not $NoInstall) {
    & $vpy (Join-Path $root 'elmer.py') --tidy
}

Write-Host ""
Write-Host "  Start ELMER with:" -ForegroundColor Cyan
Write-Host "      .\elmer.cmd"
Write-Host "  then open http://localhost:5000"
Write-Host ""
