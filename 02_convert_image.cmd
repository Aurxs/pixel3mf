@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0windows\convert.ps1"
set "result=%errorlevel%"
echo.
pause
exit /b %result%
