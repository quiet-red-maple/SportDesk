@echo off
REM [INPUT]: full project + packaging/run_win.bat
REM [OUTPUT]: starts the web UI, does NOT create exe
REM [POS]: repo root launcher
REM [PROTOCOL]: On change, update this header, then check CLAUDE.md
echo.
echo This does NOT create an exe.
echo To build exe, double-click the other bat: build windows app
echo.
call "%~dp0packaging\run_win.bat"
