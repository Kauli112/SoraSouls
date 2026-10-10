@echo off
rem SoraSouls - install + enable the Soulstruct Blender extension (verified zip: io_soulstruct-3.2.1.zip)
set "BL="
for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set "BL=%%D\blender.exe"
if not defined BL (echo Blender not found & pause & exit /b 1)
set "ZIP=%~dp0..\work\io_soulstruct-3.2.1.zip"
set "LOG=%~dp0..\work\soulstruct_install_log.txt"
if not exist "%ZIP%" (echo Missing %ZIP% & pause & exit /b 1)
echo Close Blender if it is open, then press a key.
pause
echo === install === > "%LOG%"
"%BL%" --command extension install-file --repo user_default --enable "%ZIP%" >> "%LOG%" 2>&1
echo === verify === >> "%LOG%"
"%BL%" --background --python-expr "import addon_utils, bpy; print(\"SOULSTRUCT_CHECK\", addon_utils.check(\"bl_ext.user_default.io_soulstruct\"), bpy.app.version_string)" >> "%LOG%" 2>&1
echo Done. Log: work\soulstruct_install_log.txt
pause
