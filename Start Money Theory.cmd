@echo off
setlocal
"%~dp0runtime\python.exe" "%~dp0launcher.py" %*
if errorlevel 1 pause
endlocal
