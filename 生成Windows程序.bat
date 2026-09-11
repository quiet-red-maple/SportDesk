@echo off
REM [INPUT]: full project + packaging/build_win.bat
REM [OUTPUT]: Desktop SportDesk.exe (Windows only)
REM [POS]: repo root packer
REM [PROTOCOL]: On change, update this header, then check CLAUDE.md
echo.
echo This WILL try to create an exe on Desktop\SportDesk
echo Keep the black window open.
echo.
call "%~dp0packaging\build_win.bat"
