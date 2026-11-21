#!/bin/bash
# Build the six A7S III write libraries from the A7 IV helper's source (helper/readcheck.c), with this build's tables and constants.
# usage: build_s3_write.sh        (writes libJit_s3_L<level>.so for levels 5 6 16 17 19 20 into this folder)
# Flags are those of helper/rebuild.sh. Differences from an A7 IV build: the headers of gen_s3_write.py, the A7S III libsencore.so to
# link against, and for levels 5/6 the sensor object's address and the offset of its drive-parameter pointer (modding/A7S3_PORT.md).
set -e
H="$(cd "$(dirname "$0")" && pwd)"
SEN="$H/../../../work/extracted/a7s3_501/0700_part_image/dev/nflasha15/lib/libsencore.so"
cd "$H/../helper"
CC=(../../../work/venv_zig/Scripts/python.exe -m ziglang cc -target aarch64-linux-gnu -std=gnu11 -O1 -Wall -Wextra -Werror -fPIC -shared -nostdlib -ffreestanding
    -fno-stack-protector -fno-builtin -fno-asynchronous-unwind-tables -Wl,-soname,libJit.so -Wl,--no-undefined -Wl,-z,now -g0 -s -Wl,-z,max-page-size=4096)
for L in 5 6; do
  "${CC[@]}" -DLEVEL=$L '-DSITES_H="expected_sites_ogsq_s3_v2.h"' '-DDESIGN_LABEL="ogsq_s3_v2"' -DIMAGER=0x12a41f0UL -DCTRL_DRVPARAM=0x698U \
    '-DSITES_TEXT="14"' '-DALL_TEXT="15"' readcheck.c "$SEN" -o "$H/libJit_s3_L$L.so"
done
for L in 16 17; do
  "${CC[@]}" -DLEVEL=$L '-DWORDS_H="expected_words_outsz2560_s3_v1.h"' readcheck.c "$SEN" -o "$H/libJit_s3_L$L.so"
done
for L in 19 20; do
  "${CC[@]}" -DLEVEL=$L '-DMP_H="expected_mp_ogfile2560_hs_s_s3_v1.h"' -DAVCAM_PHYS=0x401000000UL readcheck.c -o "$H/libJit_s3_L$L.so"
done
cd "$H"
for L in 5 6 16 17 19 20; do echo "$(sha256sum libJit_s3_L$L.so | cut -d' ' -f1) $(stat -c %s libJit_s3_L$L.so) level $L"; done
