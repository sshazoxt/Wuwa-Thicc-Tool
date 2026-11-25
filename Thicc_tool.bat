@echo off
setlocal
cd /d "%~dp0thicc_tool"

set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%PS%" (
 echo Windows PowerShell 5.1 is required. See docs\README_007.txt.
 pause
 exit /b 1
)

"%PS%" -NoProfile -Command "if ($PSVersionTable.PSVersion -lt [version]'5.1') { exit 1 }"

if errorlevel 1 (
 echo Windows PowerShell 5.1 is required.
 pause
 exit /b 1
)

start "" "%PS%" -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0thicc_tool\launcher.ps1"