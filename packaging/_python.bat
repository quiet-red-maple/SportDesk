@echo off
REM [INPUT]: python on PATH or common install dirs
REM [OUTPUT]: runs real python.exe with the same arguments
REM [POS]: packaging helper, skip Microsoft Store stub
REM [PROTOCOL]: On change, update this header, then check CLAUDE.md
setlocal

where py >nul 2>&1
if errorlevel 1 goto :try_dirs
py -3 -c "import sys" >nul 2>&1
if errorlevel 1 goto :try_dirs
py -3 %*
exit /b %ERRORLEVEL%

:try_dirs
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" goto :p314
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" goto :p313
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" goto :p312
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" goto :p311
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" goto :p310
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" goto :p39
goto :try_where

:p314
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" %*
exit /b %ERRORLEVEL%
:p313
"%LOCALAPPDATA%\Programs\Python\Python313\python.exe" %*
exit /b %ERRORLEVEL%
:p312
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" %*
exit /b %ERRORLEVEL%
:p311
"%LOCALAPPDATA%\Programs\Python\Python311\python.exe" %*
exit /b %ERRORLEVEL%
:p310
"%LOCALAPPDATA%\Programs\Python\Python310\python.exe" %*
exit /b %ERRORLEVEL%
:p39
"%LOCALAPPDATA%\Programs\Python\Python39\python.exe" %*
exit /b %ERRORLEVEL%

:try_where
for /f "delims=" %%I in ('where python 2^>nul') do (
  echo %%I | findstr /i /c:"WindowsApps" >nul
  if errorlevel 1 (
    "%%I" %*
    exit /b %ERRORLEVEL%
  )
)

echo [FAIL] Python not found.
echo Install 64-bit from https://www.python.org/downloads/windows/
echo MUST check: Add python.exe to PATH
echo Then close this window and run again.
pause
exit /b 1
