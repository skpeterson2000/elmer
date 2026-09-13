# Build the portable ELMER for Windows: one zip, unzip anywhere, double-click.
#
# What is in it: the program as committed (git archive, so nothing of this
# machine's - no data the operator made, no venv, no .git), the official
# embeddable Python from python.org with Flask, Pillow, reportlab and pyserial
# already in it (the embeddable Python has no pip, so the NanoVNA's library
# goes in now or never), and elmer.cmd, which starts the bundled Python and opens a browser
# window on ELMER once it is serving. No Python to install, no administrator
# rights, no execution policy to get past, nothing to answer.
#
# Why this and not an .exe: an unsigned .exe from the internet gets Windows'
# "unrecognized app" screen, and getting past it is hidden on purpose - a
# wall in front of exactly the person this is for. The embeddable Python is
# signed by the Python Software Foundation, and a zip is a zip.
#
# What it cannot do is update itself: there is no git in it. The dashboard
# says so, and install.ps1 - which is in the zip - offers git and then the
# connect step, after which the copy is an ordinary checkout that updates
# like every other. BUILD.json carries the commit it was made from, so a
# report from a portable copy still names its build.
#
#     powershell -ExecutionPolicy Bypass -File tools\build_windows_zip.ps1
#     ... -Out dist          where the zip goes (default: dist)
#
# Needs: git, and a Python with pip (any 3.9+; the packages are fetched for
# the embedded 3.12, not for it). Run from the checkout, on Windows or not -
# the CI job runs it on a Windows runner and attaches the zip to the release.

[CmdletBinding()]
param(
    [string]$Out = 'dist',
    [string]$PythonVersion = '3.12.7',
    [switch]$KeepBuild
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root 'build\ELMER'
$dist = Join-Path $root $Out
$embed = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$short = ($PythonVersion -split '\.')[0..1] -join ''      # 3.12.7 -> 312

function Say ($m) { Write-Host "  $m" }

Say "ELMER portable build, from $root"
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force $build | Out-Null
New-Item -ItemType Directory -Force $dist | Out-Null

# ------------------------------------------------------------- the program
# Committed files only. The archive is what a clone has, minus .git.
Say "the program, as committed"
$tar = Join-Path $env:TEMP 'elmer-src.tar'
& git -C $root archive --format=tar --output=$tar HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
& tar -xf $tar -C $build
if ($LASTEXITCODE -ne 0) { throw "could not unpack the archive" }
Remove-Item $tar

# The tests and the tooling are not the program.
foreach ($drop in @('tests', '.github', '.flake8', 'systemd', 'install.sh')) {
    $p = Join-Path $build $drop
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}

# ------------------------------------------------------------ the stamp
$commit = (& git -C $root rev-parse --short HEAD).Trim()
$subject = (& git -C $root log -1 --format=%s).Trim()
$date = (& git -C $root log -1 --format=%cs).Trim()
@{
    commit = $commit; subject = $subject; date = $date
    built = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm') + ' UTC'
    python = $PythonVersion; kind = 'portable-windows'
} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $build 'BUILD.json')
Say "built from $commit - $subject"

# ------------------------------------------------------------- python
Say "python $PythonVersion, embeddable, from python.org"
$pyzip = Join-Path $env:TEMP "python-$PythonVersion-embed-amd64.zip"
if (-not (Test-Path $pyzip)) {
    Invoke-WebRequest -Uri $embed -OutFile $pyzip -UseBasicParsing
}
$pydir = Join-Path $build 'python'
Expand-Archive -Path $pyzip -DestinationPath $pydir -Force

# The embeddable Python looks only where its ._pth says. It must say: its
# own zip of the standard library, its own folder, the site-packages the
# packages go into, and ELMER's folder - and it must import site, which the
# file ships with commented out.
$pth = Join-Path $pydir "python$short._pth"
@(
    "python$short.zip",
    ".",
    "Lib\site-packages",
    "..",
    "import site"
) | Set-Content -Encoding ascii $pth

# ------------------------------------------------------------ packages
# Fetched for the embedded interpreter - its version, its platform, wheels
# only - by whatever pip this machine has. That is what lets the build run
# on a machine whose own Python is some other version.
Say "Flask, Pillow, reportlab and pyserial, for the embedded python"
$site = Join-Path $pydir 'Lib\site-packages'
New-Item -ItemType Directory -Force $site | Out-Null
$pip = $null
foreach ($try in @(@('py', '-3'), @('python'), @('python3'))) {
    if (Get-Command $try[0] -ErrorAction SilentlyContinue) { $pip = $try; break }
}
if (-not $pip) { throw "no Python with pip on this machine to fetch the packages with" }
$pipArgs = @()
if ($pip.Count -gt 1) { $pipArgs = $pip[1..($pip.Count - 1)] }
& $pip[0] @pipArgs -m pip install --quiet --target $site `
    --only-binary=:all: --platform win_amd64 --implementation cp `
    --python-version ($PythonVersion -replace '\.\d+$', '') `
    -r (Join-Path $root 'requirements.txt') pyserial
if ($LASTEXITCODE -ne 0) { throw "pip could not fetch the packages for the embedded python" }
Get-ChildItem $site -Directory -Filter '*.dist-info' | ForEach-Object { Say "  $($_.Name -replace '\.dist-info$','')" }

# --------------------------------------------------------------- the zip
$name = "ELMER-windows-$commit.zip"
$zip = Join-Path $dist $name
if (Test-Path $zip) { Remove-Item $zip }
Say "zipping"
Compress-Archive -Path (Join-Path $build '*') -DestinationPath $zip -CompressionLevel Optimal
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Say "$zip  ($mb MB)"
if (-not $KeepBuild) { Remove-Item -Recurse -Force (Split-Path $build) }
Write-Host ""
Write-Host "  Unzip it anywhere and double-click elmer.cmd." -ForegroundColor Cyan
Write-Host ""
