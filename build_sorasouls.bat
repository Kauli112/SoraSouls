@echo off
rem SoraSouls - build the mod from your own Dark Souls Remastered and Kingdom Hearts II files and install it.
setlocal
cd /d "%~dp0"
set "PY=%~dp0python\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (echo Python not found next to this file. & pause & exit /b 1)
"%PY%" "%~dp0tools\build_sorasouls.py" %*
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
