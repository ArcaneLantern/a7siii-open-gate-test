# Port notes: A7 IV 6.02 open gate → A7S III 5.01

State on 2026-11-21. Everything below was read from the two firmware updates or emulated from them. The tables below are that offline state; what a camera has since confirmed is in "Camera results so far" at the end. **The write step has not run on an A7S III.** Each row says how far it is known:

- **verified offline**: the firmware's own code was run in emulation, or the bytes were compared directly
- **matched**: found by comparing code or tables with the A7 IV; not run
- **inferred**: a reading of the data with no independent check
- **needs camera**: only a read on a camera can answer it

The patch designs are in `windows/tools/modding/designs/`.

## What the A7 IV patch does, and its A7S III counterpart

| Step on the A7 IV | A7S III counterpart | State |
|---|---|---|
| 1. Enlarge the raw-frame write buffer (`dmmwb4688_v1`) | Probably not needed: the unit is 26,214,400 bytes and a full-height frame is about 4300 × 2876 | needs camera (the line size is unread) |
| 2. Full-height sensor read-out, squeezed into the stock 4K picture (`ogsq_v3`) | `ogsq_s3_v1`: 12 sensor cells, the two 4K image-mode records, the stored drive-parameter record | see below |
| 3. Output size 3840×2160 → 3840×2560 (`outsz2560_v1`) | `outsz2560_s3_v1`: one word at `0x13ec2e4` | verified offline |
| 4. Encoder side (`ogfile2560_hs_s_v1`) | `ogfile2560_hs_s_s3_v1`: 4 sites in `libmpr.so`, 101 in `av-cam.bin` | verified offline, one assumption |
| 5, 6. Rear screen 3:2 and de-squeeze key | Left out: the A7S III has its own de-squeeze display | — |

## Encoder side

- All four `libmpr.so` sites sit at the A7 IV offset +0x1150; 100 of 101 `av-cam.bin` sites at +0xA02C. The encoder-request table, the 689 descriptors, both profile tables and the memory-class table are byte-identical between the cameras. *verified offline*
- The clip-format table is at `0x38BBDC` with different codes: 8192×4320 is code 3 and 3840×2160 is code 23 (A7 IV: 1 and 16). The design turns the 8192×4320 row into 3840×2560 with code 23. *verified offline* for the table; that no A7S III format uses the 8192×4320 row is *inferred* from the A7 IV.
- The encoder's memory ids for the 4K class have the same sizes as on the A7 IV, and the class above 8.8 megapixels still lacks memory, so "row 3 := row 2" is needed here too. *verified offline*

## Sensor and image pipeline

The A7S III's image processor uses the same 3000-byte image-mode records as the A7 IV. Its own register-packing code, run with the A7 IV's rules, reproduces every stored word of its stock 4K records. *verified offline*

| Item | A7 IV | A7S III | State |
|---|---|---|---|
| Sensor | IMX710, 30 drive modes | IMX510, 40 drive modes | verified offline |
| 4K 24p mode | `0x8c0`, index 10, 7008×3942 from row 366 | `0x8c0`, index 12, 4240×2392 from row 220 | verified offline |
| Full height | 7008×4672 | 4240×2832 | verified offline |
| Line time at 24p | tight | ample (618 of 5,628 line periods used) | verified offline |
| 4K image-mode records | `0xBF7638` / `0xBF81F0` | `0xBD80E0` / `0xBD8C98` | verified offline |
| Stored record of the mode | `0x1fd1fbc` | `0x1fe1554` (`0x1fe0504` + 12 × 0x15c) | matched; record emulated |
| Movie size table | `0x143c784` | `0x13ec2ac`, same contents | verified offline |

Three things differ in kind and carry the risk:

1. **Sensor read-out switch — inferred.** On the A7 IV, 4K and a full-height mode share their timing registers, so the patch simply selects the other register column. The IMX510 has no such pair: its full-height columns differ from the 4K column in 40 to 100 registers. The design instead changes four cells of the 4K column that look like the vertical-window setting (they are zero or a constant in every full-height column and vary with the crop across the cropped ones): matrix rows 6, 7, 24, 42, column 11. That column is shared by ten 4K modes, so all of them read full height while the patch is applied. The dump's register shadow will show whether the camera's registers are what the file says.
2. **Squeeze ratio — computed, not emulated.** The stock fit already trims 4240×2392 to 2385 rows. The design sets the vertical sampling ratio to 16/19 so that 2832 rows count as 2384.8 and every row is kept (27/32, the A7 IV's value, would lose about 5 rows). The A7 IV's fit emulation is not yet ported to this build.
3. **Unset register areas.** 49 of the 154 height-dependent record fields the A7 IV sets are zero in the A7S III's stock records; they are left zero. The other 105 follow the A7 IV's rule exactly.

25p: the A7S III has modes `0x2820` / `0x28c0` beside `0x820` / `0x8c0`; which one 25p uses is not known. The design is 23.98p only.

## What the read-only steps answer

| Question | Where in the result |
|---|---|
| Is this the 5.01 software the port was made from? | SHA-256 of three libraries as loaded, and of four pages of image-processor code |
| Does the service route work on this body? | The run itself; USB ids in the session log |
| Do all sites hold their stock bytes? | STOCK / TARGET / OTHER per site (18 image-processor sites, 4 + 101 encoder sites) |
| Is the encoder program where the port assumes (`0x401000000`)? | The kernel command line, and the guard hashes |
| Is the emulated stored record right? | `stored_record` (reported, not counted) and all 40 records in the dump |
| Are the sensor registers as the file's matrix says? | Dump: register shadow against each matrix column |
| Is the size table as emulated? | Dump, after a movie mode has run (it is zero before) |
| Any trouble logged by the image processor? | Dump: its kprint and boot logs |

Still open after that, for the write step: room in the raw write buffer at full height, the image processor's working-state addresses for a read-back after applying, and the PAL mode.

## Camera results so far (one A7S III, firmware 5.01, 2026-11-21)

Three read-only runs: a check and a dump in the stills state, and a dump after a 4K 24p recording with the dial left on movie.

| Question | Answer from the camera |
|---|---|
| Does the service route work on this body? | Yes: service device 054C:0336, same commands as the A7 IV; the helper was loaded and removed cleanly each time |
| Is it the 5.01 software? | Yes: three libraries and four image-processor code pages equal the update |
| Do all sites hold their stock bytes? | Yes: 12 sensor cells, both 4K records, 4 + 101 encoder sites |
| Is the encoder program at `0x401000000`? | Yes: kernel command line and loader parameter both say so |
| Is the emulated stored record right? | At the 17 bytes the design changes, yes, before and after a recording. The camera fills 3 to 23 other bytes as it runs; the write step leaves those alone |
| Is the size table as emulated? | Yes; the output-size word and its guards are stock also in the stills state |
| Are the sensor registers as the file's table says? | Yes. In 4K 24p the register state equals the 4K column in 480 of 489 rows (the rest are run-time values), and the four cells the design replaces hold the table's values 20, 14, 64, 1. In the stills state they hold 22, 0, 0, 0 |

The first helper build reported NOT READY on this stock camera because it compared the first 4,096 bytes of the encoder program with the file; that page is not constant in memory. The guard was replaced (helper v2).

Not answered by any read, and so tested for the first time by the write step:

- that the four register cells are the whole vertical-window setting of the IMX510 (they reach the sensor; that the sensor then reads full height is inferred)
- room in the raw-frame write buffer at full height
- the squeeze ratio 16/19 in the camera's own resize fit
- the pointer chain the sensor step follows to the stored record (if it is wrong the step writes nothing)
- the encoder at 2,560 rows on this body (same tables and codec firmware as the A7 IV, where it works)

The write step is the A7 IV helper's own write code (`helper/readcheck.c`, levels 5/6, 16/17, 19/20) built with this camera's tables (`helper_s3/gen_s3_write.py`, `build_s3_write.sh`). Offline it was run in emulation on the stored record exactly as this camera held it in all three runs: applied, put back byte for byte.
