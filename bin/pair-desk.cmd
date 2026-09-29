@echo off
rem Pair Desk launcher for Windows: runs desk.py with the first Python 3.11+ found.
rem Order: %PAIR_DESK_PYTHON%, py -3, python, python3. Arguments, stdin and the exit code pass through.
rem The Claude Code plugin, the Codex and opencode integrations and the docs start the desk through
rem this file (or bin/pair-desk on macOS and Linux), so `python` vs `python3` never matters.
setlocal
set "DESK=%~dp0..\desk.py"
if defined PAIR_DESK_PYTHON (
  set PY="%PAIR_DESK_PYTHON%"
  goto run
)
call :try py -3 && goto run
call :try python && goto run
call :try python3 && goto run
echo Pair Desk needs Python 3.11 or newer: install it from https://www.python.org/downloads/ 1>&2
echo (or set PAIR_DESK_PYTHON to a python.exe). 1>&2
exit /b 9009

:try
%* -I -S -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul || exit /b 1
set PY=%*
exit /b 0

:run
%PY% "%DESK%" %*
exit /b %ERRORLEVEL%
