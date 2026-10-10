@echo off
rem SoraSouls - swap Sora into Knight armor parts (exports to work\export_sora only)
set "BL="
for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set "BL=%%D\blender.exe"
if not defined BL (echo Blender not found & pause & exit /b 1)
set "SORASOULS_ROOT=%~dp0.."
"%BL%" --background --python "%~dp0blender_swap_sora.py" > "%~dp0..\work\swap_log.txt" 2>&1
echo Done. Report: work\swap_report.txt
pause
