@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install.ps1"
set "result=%errorlevel%"
echo.
pause
exit /b %result%
