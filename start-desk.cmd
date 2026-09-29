@echo off
rem Pair Desk: double-click to start the desk and open it in the browser.
rem Close this window (or press Ctrl+C) to stop it.
title Pair Desk
call "%~dp0bin\pair-desk.cmd" serve --open %*
if errorlevel 1 pause
