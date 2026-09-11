@echo off
REM [INPUT]: Windows Python + pip + PyInstaller
REM [OUTPUT]: Desktop\SportDesk\SportDesk.exe and a Desktop shortcut
REM [POS]: packaging Windows packer, must run on Windows
REM [PROTOCOL]: On change, update this header, then check CLAUDE.md
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PYBAT=%~dp0_python.bat"
set "OUT=C:\SportDeskBuild"

echo.
echo ============================================
echo  Building SportDesk.exe
echo  Keep this window open. First run is slow.
echo  EXE will be on Desktop\SportDesk
echo ============================================
echo.

if not exist "%ROOT%\sport_desk.py" (
  echo [FAIL] Missing sport_desk.py
  echo Copy the WHOLE project folder, not only packaging.
  pause
  exit /b 1
)

echo [1/4] pip packages
call "%PYBAT%" -m pip install -r "%ROOT%\requirements.txt" -i %MIRROR%
if errorlevel 1 (
  echo [FAIL] pip failed, no exe
  pause
  exit /b 1
)
call "%PYBAT%" -m pip install pyinstaller -i %MIRROR%
if errorlevel 1 (
  echo [FAIL] PyInstaller install failed, no exe
  pause
  exit /b 1
)

if not exist "%OUT%" mkdir "%OUT%"

echo [2/4] PyInstaller (please wait)
call "%PYBAT%" -m PyInstaller --noconfirm --clean --distpath "%OUT%\dist" --workpath "%OUT%\build" "%ROOT%\packaging\SportDesk.spec"
if errorlevel 1 (
  echo [FAIL] pack failed, no exe. Scroll up for English errors.
  pause
  exit /b 1
)

set "EXE=%OUT%\dist\SportDesk\SportDesk.exe"
if not exist "%EXE%" (
  echo [FAIL] SportDesk.exe was not created
  explorer "%OUT%\dist"
  pause
  exit /b 1
)

echo [3/4] Copy to Desktop
set "DESK=%USERPROFILE%\Desktop"
if exist "%USERPROFILE%\OneDrive\Desktop" set "DESK=%USERPROFILE%\OneDrive\Desktop"
set "DEST=%DESK%\SportDesk"
if exist "%DEST%" rmdir /s /q "%DEST%"
mkdir "%DEST%"
xcopy /e /i /y "%OUT%\dist\SportDesk" "%DEST%" >nul
echo Double-click SportDesk.exe > "%DEST%\README.txt"

echo [4/4] Desktop shortcut
powershell -NoProfile -Command "$desk=$env:USERPROFILE+'\Desktop'; if (Test-Path ($env:USERPROFILE+'\OneDrive\Desktop')) { $desk=$env:USERPROFILE+'\OneDrive\Desktop' }; $exe=Join-Path $desk 'SportDesk\SportDesk.exe'; $lnk=Join-Path $desk 'SportDesk.lnk'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($lnk); $s.TargetPath=$exe; $s.WorkingDirectory=(Join-Path $desk 'SportDesk'); $s.Save()"

echo.
echo ============================================
echo  OK. Look at your DESKTOP:
echo    folder:  SportDesk
echo    file:    SportDesk\SportDesk.exe
echo    shortcut: SportDesk.lnk
echo  Full path:
echo    %DEST%\SportDesk.exe
echo ============================================
echo.
explorer /select,"%DEST%\SportDesk.exe"
pause
exit /b 0
