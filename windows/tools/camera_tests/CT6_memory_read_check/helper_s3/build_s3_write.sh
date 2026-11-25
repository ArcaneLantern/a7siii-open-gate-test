#!/bin/bash
# Build the A7S III write libraries from the A7 IV helper's source (helper/readcheck.c), with this build's tables and constants.
# usage: build_s3_write.sh        (writes libJit_s3_<step>.so into this folder; L19/L20 use ogfile2560_hs_s_s3_v2, N19 uses ogfile2560_hs_s_s3_v1)
# Flags are those of helper/rebuild.sh. Differences from an A7 IV build: the headers of gen_s3_write.py, the A7S III libsencore.so to
# link against, and for levels 5/6 the sensor object's address and the offset of its drive-parameter pointer (modding/A7S3_PORT.md).
set -e
H="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${S3_LIBSENCORE:-}" ]; then
  SEN="$S3_LIBSENCORE"
elif [ -f "$H/../../../work/extracted/a7s3_501/0700_part_image/dev/nflasha15/lib/libsencore.so" ]; then
  SEN="$H/../../../work/extracted/a7s3_501/0700_part_image/dev/nflasha15/lib/libsencore.so"
else
  SEN="$H/../../../../../../firmwares/a7siii/ghidra_targets/libsencore.so"
fi
if [ -n "${ZIG_PYTHON:-}" ]; then
  PY="$ZIG_PYTHON"
elif [ -x "$H/../../../work/venv_zig/Scripts/python.exe" ]; then
  PY="$H/../../../work/venv_zig/Scripts/python.exe"
else
  PY="python3"
fi
cd "$H/../helper"
CC=("$PY" -m ziglang cc -target aarch64-linux-gnu -std=gnu11 -O1 -Wall -Wextra -Werror -fPIC -shared -nostdlib -ffreestanding
    -fno-stack-protector -fno-builtin -fno-asynchronous-unwind-tables -Wl,-soname,libJit.so -Wl,--no-undefined -Wl,-z,now -g0 -s -Wl,-z,max-page-size=4096)
for L in 5 6; do
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogsq_s3_v5.h"' '-DDESIGN_LABEL="ogsq_s3_v5"' -DIMAGER=0x12a41f0UL -DCTRL_DRVPARAM=0x698U \
    readcheck.c "$SEN" -o "$H/libJit_s3_L$L.so"
done
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_outsz2560_s3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_s3_L$L.so"
done
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile2560_hs_s_s3_v2.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_s3_L$L.so"
done
"${CC[@]}" -DLEVEL=19 '-DMP_H="expected_mp_ogfile2560_hs_s_s3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_s3_N19.so"
# The rear-screen steps (modding/A7S3_PORT.md sections 26 and 27): the same levels with other tables. S = screen ratio words, C = C3 routine in appFw.so.
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_lcdratio32_s3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_s3_S$L.so"
done
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_lcdcycle_s3_v3.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_s3_C$L.so"
done
cd "$H"
hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}
for L in 5 6 16 17 19 20; do echo "$(hash_file libJit_s3_L$L.so) $(wc -c < libJit_s3_L$L.so | tr -d ' ') level $L"; done
for N in S16 S17 C19 C20 N19; do echo "$(hash_file libJit_s3_$N.so) $(wc -c < libJit_s3_$N.so | tr -d ' ') step $N"; done
