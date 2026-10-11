#!/bin/sh
# Builds sora_glide.dll with clang + lld-link only (no Windows SDK / C runtime needed).
set -e
cd "$(dirname "$0")"
mkdir -p build
llvm-dlltool-18 -m i386:x86-64 -d kernel32.def -l build/kernel32.lib
llvm-dlltool-18 -m i386:x86-64 -d user32.def -l build/user32.lib
llvm-dlltool-18 -m i386:x86-64 -d gdi32.def -l build/gdi32.lib
llvm-rc-18 /FO build/sora_glide.res sora_glide.rc
clang --target=x86_64-pc-windows-msvc -O2 -ffreestanding -fno-builtin -fno-stack-protector -mno-stack-arg-probe \
      -Wall -Wno-parentheses -c sora_glide.c -o build/sora_glide.obj
lld-link /dll /nodefaultlib /entry:DllMain /machine:x64 /subsystem:windows build/sora_glide.obj \
      build/kernel32.lib build/user32.lib build/gdi32.lib build/sora_glide.res /out:build/sora_glide.dll
echo built build/sora_glide.dll
