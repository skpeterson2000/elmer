@echo off
rem Start ELMER on Windows, from wherever this file is - and open it.
rem
rem Three Pythons, in the order that needs the least of the machine: the one
rem bundled in a portable ELMER (python\ beside this file - nothing to install
rem at all), the virtual environment install.ps1 builds, and finally a system
rem Python, so a copy that has never been installed still runs - it will
rem complain about a missing Flask rather than about a missing launcher,
rem which is the more useful complaint.
rem
rem --open puts ELMER in this machine's browser once it is serving, so a
rem double-click ends in a window and not in a console saying where to go.
rem Anything else on the command line goes through as it is.
setlocal
title ELMER
cd /d "%~dp0"
if exist "python\python.exe" (
    "python\python.exe" elmer.py --open %*
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" elmer.py --open %*
) else (
    py -3 elmer.py --open %*
)
rem A double-clicked window closes the instant the program ends, taking the
rem error with it - so when ELMER stops with one, the window stays until a
rem key is pressed and the message above it can be read, or photographed.
if errorlevel 1 (
    echo.
    echo   ELMER stopped with an error. The message above says why.
    echo   If it says "No module named" something, or that Python is not
    echo   recognized, this copy has not been installed yet: open PowerShell
    echo   in this folder and run
    echo       powershell -ExecutionPolicy Bypass -File install.ps1
    echo   then double-click this again.
    echo.
    pause
)
endlocal
