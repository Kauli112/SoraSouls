@echo off
rem SoraSouls - run the Sora fitting script in Blender (no window)
set "BL="
for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set "BL=%%D\blender.exe"
if not defined BL (echo Blender not found in C:\Program Files\Blender Foundation & pause & exit /b 1)
echo Using %BL%
set "SORASOULS_ROOT=%~dp0.."
"%BL%" --background --factory-startup --python "%~dp0blender_fit_sora.py" > "%~dp0..\work\sora\blender_log.txt" 2>&1
echo Done. Log: work\sora\blender_log.txt
pause
