@echo off
REM [INPUT]: Windows Python 3.9+
REM [OUTPUT]: local UI at http://127.0.0.1:8787  (no exe)
REM [POS]: packaging Windows runner
REM [PROTOCOL]: On change, update this header, then check CLAUDE.md
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "VENV=C:\SportDeskRun"
set "PYBAT=%~dp0_python.bat"

echo.
echo ============================================
echo  SportDesk  (Windows)
echo  This is a BROWSER app, not a window app.
echo  Wait, then open:  http://127.0.0.1:8787
echo  This script does NOT create an exe.
echo ============================================
echo.

if not exist "%ROOT%\sport_desk.py" (
  echo [FAIL] Missing sport_desk.py
  echo Copy the WHOLE project folder, not only packaging.
  pause
  exit /b 1
)

echo [1/2] Creating venv at %VENV%
if not exist "%VENV%\Scripts\python.exe" (
  call "%PYBAT%" -m venv "%VENV%"
  if errorlevel 1 (
    echo [FAIL] venv failed
    pause
    exit /b 1
  )
)

echo Installing packages, first time takes a few minutes...
"%VENV%\Scripts\python.exe" -m pip install -r "%ROOT%\requirements.txt" -i %MIRROR%
if errorlevel 1 (
  echo [FAIL] pip failed. Turn off VPN and retry.
  pause
  exit /b 1
)

echo.
echo [2/2] Starting. Browser should open in 3 seconds.
echo Keep this black window OPEN.
echo.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8787"
"%VENV%\Scripts\python.exe" -m agent --web --host 127.0.0.1 --port 8787
echo.
echo Stopped. If no page, paste this in Chrome/Edge:
echo http://127.0.0.1:8787
pause
exit /b 0
