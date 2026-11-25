@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
 start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0thicc_tool_gui.pyw"
 exit /b
)
echo Environment not found. Run Thicc_tool.bat first.
echo Alternatively enter the full path to an existing compatible python.exe or pythonw.exe with dependencies already installed.
set /p "PY=Python path: "
if not defined PY exit /b 1
set "PY=%PY:"=%"
if not exist "%PY%" (echo Python not found. & pause & exit /b 1)
"%PY%" "%~dp0thicc_tool_gui.pyw"
