@echo off
rem Builds sora_glide.dll on Windows with LLVM (clang + lld-link only, no Windows SDK / C runtime) - same steps as build.sh.
setlocal
set "LLVM=C:\Program Files\LLVM\bin"
if not exist "%LLVM%\clang.exe" (echo LLVM not found in %LLVM% & exit /b 1)
cd /d "%~dp0"
if not exist build mkdir build
"%LLVM%\llvm-dlltool.exe" -m i386:x86-64 -d kernel32.def -l build\kernel32.lib || exit /b 1
"%LLVM%\llvm-dlltool.exe" -m i386:x86-64 -d user32.def -l build\user32.lib || exit /b 1
"%LLVM%\llvm-dlltool.exe" -m i386:x86-64 -d gdi32.def -l build\gdi32.lib || exit /b 1
"%LLVM%\llvm-rc.exe" /FO build\sora_glide.res sora_glide.rc || exit /b 1
"%LLVM%\clang.exe" --target=x86_64-pc-windows-msvc -O2 -ffreestanding -fno-builtin -fno-stack-protector -mno-stack-arg-probe ^
    -Wall -Wno-parentheses -c sora_glide.c -o build\sora_glide.obj || exit /b 1
"%LLVM%\lld-link.exe" /dll /nodefaultlib /entry:DllMain /machine:x64 /subsystem:windows build\sora_glide.obj ^
    build\kernel32.lib build\user32.lib build\gdi32.lib build\sora_glide.res /out:build\sora_glide.dll || exit /b 1
echo built build\sora_glide.dll
