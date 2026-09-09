@echo off
rem Start ELMER on Windows, from wherever this file is.
rem
rem Prefers the virtual environment install.ps1 builds, and falls back to a
rem system Python so a copy that has never been installed still runs - it will
rem complain about a missing Flask rather than about a missing launcher, which
rem is the more useful complaint.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" elmer.py %*
) else (
    py -3 elmer.py %*
)
endlocal
