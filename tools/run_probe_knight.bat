@echo off
rem SoraSouls - probe Knight armor with the Soulstruct add-on (writes only into work\)
set "BL="
for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set "BL=%%D\blender.exe"
if not defined BL (echo Blender not found & pause & exit /b 1)
set "SORASOULS_ROOT=%~dp0.."
"%BL%" --background --python "%~dp0blender_probe_knight.py" > "%~dp0..\work\knight_probe_log.txt" 2>&1
echo Done. Report: work\knight_probe_report.txt
pause
