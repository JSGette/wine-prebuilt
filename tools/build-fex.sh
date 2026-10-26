#!/usr/bin/env bash
set -euo pipefail

source_dir=${1:?FEX source directory}
build_root=${2:?Build directory}
install_dir=${3:?Wine install directory}
root=$(cd "$(dirname "$0")/.." && pwd)
revision=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["fex"]["revision"])' "$root/sources.json")

# PE builds must not inherit the host's SDK or glibc sysroot settings.
unset CC CXX CFLAGS CXXFLAGS CPPFLAGS LDFLAGS SDKROOT MACOSX_DEPLOYMENT_TARGET
for variant in arm64ec wow64; do
    case "$variant" in
        arm64ec) triple=arm64ec-w64-mingw32; module=libarm64ecfex.dll ;;
        wow64) triple=aarch64-w64-mingw32; module=libwow64fex.dll ;;
    esac
    build_dir="$build_root/$variant"
    mkdir -p "$build_dir"
    cmake -S "$source_dir" -B "$build_dir" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$source_dir/Data/CMake/toolchain_mingw.cmake" \
        -DMINGW_TRIPLE="$triple" -DCMAKE_BUILD_TYPE=Release \
        -DENABLE_LTO=OFF -DENABLE_CCACHE=OFF -DBUILD_TESTING=OFF \
        -DBUILD_FEXCONFIG=OFF -DENABLE_JEMALLOC_GLIBC_ALLOC=OFF \
        -DENABLE_VIXL_DISASSEMBLER=OFF -DENABLE_VIXL_SIMULATOR=OFF -DENABLE_ZYDIS=OFF \
        -DTUNE_ARCH=generic -DTUNE_CPU=none -DRANGES_NATIVE=OFF \
        -DOVERRIDE_VERSION="FEX-${revision:0:12}" \
        -DCMAKE_INSTALL_PREFIX="$build_dir/install" > "$build_dir/configure.log" 2>&1
    cmake --build "$build_dir" -j "${JOBS:-4}" > "$build_dir/build.log" 2>&1
    cmake --install "$build_dir" > "$build_dir/install.log" 2>&1
    mkdir -p "$install_dir/lib/wine/aarch64-windows"
    cp "$build_dir/install/lib/$module" "$install_dir/lib/wine/aarch64-windows/"
done
