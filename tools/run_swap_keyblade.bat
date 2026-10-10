@echo off
rem SoraSouls - swap the Kingdom Key into the Broadsword (exports to work\export_keyblade only)
set "BL="
for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set "BL=%%D\blender.exe"
if not defined BL (echo Blender not found & pause & exit /b 1)
set "SORASOULS_ROOT=%~dp0.."
"%BL%" --background --python "%~dp0blender_swap_keyblade.py" > "%~dp0..\work\keyblade_log.txt" 2>&1
echo Done. Report: work\keyblade_report.txt
pause
