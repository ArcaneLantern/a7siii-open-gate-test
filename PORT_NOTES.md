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
| 2. Full-height sensor read-out, squeezed into the stock 4K picture (`ogsq_v3`) | `ogsq_s3_v3`: 19 sensor-side cells, the two 4K image-mode records, the stored drive-parameter record | see below |
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
| 4K image-mode records | `0xBF7638` / `0xBF81F0` | `0xBCFFF8` / `0xBD0BB0` (corrected, see the end) | verified offline |
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

## The first two write tests, and the correction (2026-11-22)

Two applies ran on the A7S III with sensor step v1. All three steps reported DONE, the camera stayed up and recorded 3840 × 2560. A dump taken with the patch live gave the scaler's own numbers:

- the second scaler took columns 329 to 3910 (3,581 of 4,240) and all 2,392 rows of its input picture: a width crop to 84 %
- its input picture was still the stock 4240 × 2392, and nothing in the camera core's state showed a 2,848-row stage

**Cause.** The image processor picks its picture records with a selector keyed on the drive mode and on the left or right half. For 4K 24p and 30p (`0x8c0`, `0x820`) it returns the records at `0xBCFFF8` and `0xBD0BB0`. Step v1 changed `0xBD80E0` / `0xBD8C98`, a pair with the same picture sizes that belongs to mode `0x2820`. So the sensor was switched to full height, the first stage went on taking the stock 2,408 rows, and the 16/19 ratio then cut the width of an ordinary 16:9-sized picture.

**What that takes back.** The two tests did not run the taller first stage. Room in the raw-frame buffer and the vertical squeeze in the first scaler are untested. The statement above that 49 height fields are zero on this camera was a property of the wrong pair: on the right records all 154 fields follow the A7 IV's rule.

**Step v2** (`ogsq_s3_v2`) is the same sensor cells and stored-record bytes with the two records at the right addresses. The camera's own packing code reproduces the stock words of these records, and both emulation suites pass. It has not run on a camera.

Confirmed by the two tests all the same: the write steps and their checks work on this body, the pointer chain to the stored record is right, the encoder accepts 2,560 rows, and the scaler result block is at `0x140043C`.

## Step v2 on the camera, and step v3 (2026-11-22)

**v2 ran once.** The dump taken with it applied:

- camera core: first stage 4288 × 2848, cropped to 4240 × 2832; reference window 4240 × 2832
- second scaler: takes 4240 × 2391.9 of its 4240 × 2392 input (everything); vertical scale 2392/2832
- no error line in the image processor's log: the raw-frame buffer accepted the taller frame

So the records, the 16/19 ratio and the buffer are right. But the recorded picture ended at 81 to 84 % of the height (2392/2832 is 84.5 %), with purple blacks and line artefacts: the sensor went on delivering the 16:9 band.

**Why.** Across the sensor's register table, the full-frame 4K mode, the 3840 × 2160 crop mode and the S35 mode differ from each other in the mode register and a handful of companion registers; no register holds a first or last row. The vertical window is a property of the sensor mode, as on the A7 IV's sensor. Steps v1 and v2 changed four companions and left the mode at the 4K band. (The A7 IV patch switches the mode; I had not done that here because no stock mode is "4K timing, full height".)

**Frame timing, decoded.** A timing row is HMAX, VMAX and `flag | P<<8 | E<<16`: one line in every P is E units longer, and a frame is HMAX × VMAX + (VMAX / P) × E units of 1/36 MHz. Stock 4K 24p: 266 × 5628 + 84 × 53 = 1,501,500 units = 23.976 fps. This reproduces the frame rate of all 40 drive modes.

**Step v3** (`ogsq_s3_v3`) gives drive mode `0x8c0` the sensor mode of drive mode `0xe011` (full height 4240 × 2832, one row per line, up to 36.7 fps):

| Cell | Stock | v3 |
|---|---|---|
| register table column | 11 (sensor mode `0x21`) | 1 (sensor mode `0x01`) |
| receiver type (two tables) | 5, 3 | 0, 2 (as `0xe011` and the S35 movie modes) |
| timing, 59.94 system | 266, 5628, P 67, E 53 | 312, 4788, P 57, E 91 (23.976 fps) |
| timing, 50 system | 268, 5580, P 93, E 76 | 313, 4780, P 239, E 193 (24.000 fps) |
| window top margins, height | 38, 6, 2392 | 122, 22, 2832 |
| aux stream, LC, crop, geometry rows | band values | `0xe011`'s values (offsets 0) |
| read-out table | 1384, 1372, 618, 618 | 1174, 1172, 728, 728 |
| `0xc71a24` +4 (meaning not known) | 478 | 484 |

The register table itself is no longer touched, so the other 4K modes keep their stock sensor settings. The two picture records are v2's (their frame layout is the one `0xe011`'s own records have). The stored drive-parameter record is computed by running the camera's calculator on the changed tables: 62 bytes change, none of them one the camera was seen to rewrite while running.

Guesses in v3: the `0xc71a24` value, the constant in the read-out table's frame-length fields, and the choice of P and E. Not known: whether the 4K first stage accepts one-row-per-line data, and whether the 4K 24p calibration suits the other sensor mode.

## Step v3 on the camera, and step v4 (2026-11-22)

**v3 ran once as designed** (library hashes and the dump confirm the version). After a recording the sensor's registers matched the full-height mode, the second scaler took all 2832 rows, and the log was clean. The tester compared the clip with a photo: the whole sensor area is in the file, and v2's purple cast and line artefacts are gone. Two faults in that run: the standby picture before the first recording looked like v2's (purple, lower part missing) and turned right when recording started; and the recorded picture has stepped tones.

**Then it stopped working.** After a battery pull and a new apply, on every attempt the picture flickered as soon as movie mode was entered, and the camera froze and restarted. No dump of that state exists yet.

**An error in v3's timing row.** The reading of the timing row above ("one line in every P is E units longer") was not exact. Checked on all 80 stock rows: in each of the 57 that have a fraction, E is smaller than P, P is odd and divides VMAX, VMAX is a multiple of 4, and E/P is the reduced fraction of (frame units / VMAX) − HMAX. So **E/P is the fractional part of the line length**: a line is HMAX + E/P units on average. v3's 59.94-system row, 312, 4788, P 57, E 91, asks for a fraction of 1.6. No stock row does that. The row is copied unchanged into the record that goes to the timing hardware, so what the hardware did with it is not known. If it lengthens every line by one unit, the frame rate is 24.022 instead of 23.976 fps, one frame too many about every 22 seconds; that would fit a picture that works for some seconds and then flickers and stops. This link is not shown.

**Step v4** (`ogsq_s3_v4`) is v3 with that row corrected, and nothing else:

| Cell | v3 | v4 |
|---|---|---|
| timing, 59.94 system | 312, 4788, P 57, E 91 | 313, 4788, P 57, E 34 (313.596 units per line, 23.976 fps) |

The 50-system row (313, 4780, P 239, E 193) was valid and stays. VMAX is unchanged, so the read-out table is as in v3. In the stored record four bytes change against v3 (HMAX and E, in both copies of the row). HMAX 313 is one unit above the 312 the camera uses for this sensor mode; stock runs one register column at line lengths one or two units apart (263/264/265, 266/268, 330/331). No valid row exists at exactly 312.

**Open after v4**, deliberately not changed in it so that one test answers one question:

- The two picture records still describe the frame format of the stock 4K sensor mode in several words that follow the read-out type or the line length in every stock record (for example `+0x27c`, `+0x280`, `+0x284`, `+0x294`, `+0x2a8`, and `+0x328` = 5.5 × HMAX). `0xe011`'s own records also start the picture 76 columns later. The tester's frame has a brightness step about that far in from the left edge. Whether this is behind the stepped tones is not known.
- Why the first standby differed from the recording in the one good run. The drive-mode selector (`0x411798`) takes the 24p or 30p family from the frame-rate setting and has no standby-or-recording input.

## Step v4 on the camera, and step v5 (2026-11-22)

**v4 ran without flicker and without a restart.** Two dumps came back, one in standby with the live view still wrong and one after a recording. Both hold the same configuration: every patch site at its v4 value, the stored record's timing 313, 4788, P 57, E 34, the sensor registers of the full-height mode, and the second scaler taking all 2832 rows into 3840 x 2560. So the sensor was already in the full-height mode while the live view was wrong. The only differences between the two dumps are gain and shutter values: the exposure control reacting to a wrong picture.

**The live view came right by itself** after the first dump's USB session, with no recording. The camera's event log (the coprocessor log region at `0xc0000`) shows a full start of the picture ("IMG INIT", then the live view start) after every USB session. So the fault belongs to the switch from stills live view to movie mode; a fresh start in movie mode gives the right picture. The step that the switch lacks was not found. What was found: the sensor control code picks its sequences by the class of the drive mode id (below `0xa000` movie and live view, `0xa000` and `0xe000` classes capture; `0x86cb90`, `0x86cbca`, `0x86cbf6`), and patched `0x8c0` has a movie id on a sensor mode that stock only runs under capture ids. The sensor link is restarted on every mode change whatever the receiver type (`0x335a94`), so that is not the missing step. For now the instructions have the dial on movie when the last USB session ends.

**The "receiver type" is the sensor link's bit depth.** The function that builds the link parameters (`0x336b30`) reads the second value from the mode's stored record and maps 0, 1, 2, 3 to 16, 14, 12, 10 bits per pixel (tables at `0x336bac` and `0x336bcc`). Stock 4K (5, 3) is a 10-bit link. The full-height mode and the S35 movie modes (0, 2) are 12-bit, the slow stills modes (0, 1) 14-bit. v3 and v4 made 4K 24p a 12-bit link.

**Step v5** (`ogsq_s3_v5`) is v4 with the picture records brought in line with that. In all 46 stock picture records (20 of 10-bit modes, 26 of 12- and 14-bit modes) five words take one value for a 10-bit link and another for the rest, and a sixth is the record's width word plus 9 or plus 5. No other word of the record follows the link format this way. The two records of v3 and v4 still held the 10-bit values:

| Record word | v4 (10-bit link) | v5 (12-bit link) |
|---|---|---|
| `+0x274` | `0x222` (width word + 9) | `0x21e` (width word + 5) |
| `+0x27c` | `0x20002` | 0 |
| `+0x280` | `0x30003` | 0 |
| `+0x284` | 8 | 0 |
| `+0x294` | 7 | 3 |
| `+0x2a8` | 0 | 1 |

Both records (left `0xbcfff8`, right `0xbd0bb0`) get the same six values; they are the ones the stock S35 4K movie records hold. Every sensor cell, the stored record and every other record byte are v4's.

Not shown: what the first stage does with these words, and that they are behind the stepped tones. Still open after v5: the 76-column and 16-row layout difference between the two sensor formats, the line-length words (`+0x328`, `+0x3b8`), and the switch from stills live view.
