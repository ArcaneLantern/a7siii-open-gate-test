# A7S III open gate: test kit (firmware 5.01)

<p><b>The current write tests are UNTESTED</b> they only write to ram, so should remove themselves and return the camera to stock with a battery pull, but they are again, not tested yet.</p?

This kit ports the A7 IV open-gate patch (a7iv-open-gate-test) to the Sony A7S III (ILCE-7SM3). The goal is a true 3840 × 2560 (3:2) recording in XAVC HS 4K and XAVC S 4K at 23.98p, set in the camera's memory only and gone after a battery pull.

**Where it stands (2026-11-22):**

- The two read-only steps have run on an A7S III. The camera's software and every place the patch touches were as predicted.
- The write step has run twice on an A7S III. All three steps applied, the camera stayed stable and recorded a 3840 × 2560 file, and a battery pull returned it to stock. **But the framing was wrong:** no extra height, and the width was cropped. The cause was found in the dump: the first version changed the picture records of a different video mode.
- Sensor step v2 fixed that and ran once. The camera's scaler then took the whole picture, as designed, and the raw-frame buffer had room. **But the sensor still delivered only the 16:9 band:** the lower sixth of the picture was black, blacks were purple, and there were line artefacts (also in other 4K modes while the patch was applied). On this sensor the vertical window belongs to the sensor's mode, and v2 had not changed the mode.
- Sensor step v3 gave 4K 24p the camera's own full-height sensor mode (the one it uses for fast full-frame stills read-out), with that mode's receiver settings and a new 23.976 fps frame timing. It ran on an A7S III. **In one recording the whole sensor area reached the file** (checked against a photo), with stepped tones in the picture and a wrong standby picture before the recording. **On later attempts the picture flickered as soon as movie mode was entered, and the camera froze and restarted.** A battery pull returned it to stock each time.
- We found an error of ours in v3: one value of the new frame timing was outside the range the camera's own timings use (see `PORT_NOTES.md`). It fits the flicker and the restart, but that it caused them is not shown.
- Sensor step v4 was v3 with that timing value corrected. It ran on an A7S III: **no flicker and no restart.** The dumps show the full-height sensor mode and the whole sensor area scaled to 3840 × 2560. Two faults remain from v3: stepped tones in the picture, and a wrong live view when movie mode is entered from stills (it came right at the camera's next start of the picture: after a USB session with the dial on movie, or when a recording started).
- For the stepped tones we found a mismatch of ours: the stock 4K mode reads the sensor over a 10-bit link, the full-height mode over a 12-bit one, and six words in each of the two picture records still described the 10-bit link (see `PORT_NOTES.md`). That this causes the steps is not shown.
- **This kit has sensor step v5: v4 with those record words set for the 12-bit link, and nothing else changed. It has not run on a camera yet.** It changes the recording path that worked in v4, so a wrong picture or a restart are possible again. The live view fault is handled by the order of the steps for now: see "How to run it".
- **If you ran an earlier version: pull the battery for 10 seconds before anything else.** The old patch may still be in the camera's memory, and v5 will refuse to apply on top of it.

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 5.01 software the port was made from and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | The same, plus facts for the port: memory map, the camera's own logs, sensor register state, internal tables | No |
| `open_gate_apply.cmd` | Applies the open-gate state, in three steps | **Yes: memory only** |
| `open_gate_putback.cmd` | Puts the three steps back | Yes: memory only |

Nothing in this kit writes to the camera's firmware or to its settings.

## Before you start

1. The camera's menu must show **Ver. 5.01** (Setup, Setup Option, Version). On any other version, stop and tell us the version.
2. **USB Connection Mode: Mass Storage.** If asked on connection, choose **Image Transfer (MSC)**.
3. A charged battery. Do not record or play back while a step runs.

## Windows, once

1. Install Python 3.10 or later from python.org (with the "py launcher").
2. Run `windows/setup.cmd`.
3. Install the libusb-win32 driver for the camera with [Zadig](https://zadig.akeo.ie): Options, List All Devices, pick the camera, choose libusb-win32, Replace Driver. The first run switches the camera to service mode, where it shows up as a new device (054C:0336): install the driver for that one too, then run the step again.

macOS and Android are not covered yet.

## The read-only steps

Each launcher asks for the firmware version the menu shows. Each run makes a new folder in `windows/camera_private`.

- **Check or dump in the stills state:** dial on stills, connect, run the launcher.
- **Dump of the 4K state:** set File Format XAVC S 4K (or XAVC HS 4K) at 24p, APS-C/Super 35 off, S&Q off, SteadyShot not on Active. Dial on movie, record a few seconds, stop. **Leave the dial on movie**, connect, run `dump_info.cmd`.

What they do to the camera: they switch it to service mode, write one small program file to the service partition, which the camera loads once, and delete that file again in the same session. The program only reads and creates one file, its report, on the camera's RAM disk. Its source is `windows/tools/camera_tests/CT6_memory_read_check/helper_s3/s3read.c`.

## The write step

**What it changes.** Three groups of bytes in the running camera's memory: the sensor read-out and the two 4K picture records of the image processor (full sensor height instead of the 16:9 band), one size word (3840×2160 becomes 3840×2560), and the encoder's tables for XAVC HS 4K and XAVC S 4K at 23.98p and 25p. Each step first checks that every byte it is about to change holds its stock value, writes, reads back, and undoes its own writes if anything does not match.

**What we do not know yet.** Whether the 12-bit record words remove the stepped tones, and whether the picture stays right with them. Why the live view is wrong when movie mode is entered from stills with the patch applied. How exposure and autofocus behave. The sensor is read more slowly in this mode: expect more rolling shutter (about 26 ms top to bottom). A battery pull returned the camera to stock after every fault so far.

**While it is applied:** use only XAVC HS 4K or XAVC S 4K at 24p. Other formats, frame rates, S&Q and APS-C/Super 35 are likely to fail or hang. The rear screen and viewfinder will probably look squeezed vertically: the screen picture is not corrected on this camera yet. The recorded file is what counts.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K) and 24p. APS-C/Super 35 off, S&Q off.
2. Pull the battery for 10 seconds, put it back, switch on. **Dial on stills.** Do not go into movie mode yet.
3. Connect USB and run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
4. It runs three steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until it says all three steps passed.
5. When it says all three steps passed: **turn the dial to movie first, then unplug USB.** The camera then starts its picture directly in movie mode. **Watch the picture for 30 seconds without recording** and note what it shows (normal, purple, part missing, flicker).
6. If it is still running: **leave the dial on movie**, connect USB and run `windows/dump_info.cmd`. This is the standby dump, taken before any recording. Unplug again. If the live view was wrong in step 5, it should be right after this (it was in the v4 test). Please tell us which it was.
7. Record 20 to 30 seconds, stop, and play the clip back. For the stepped tones, a dark scene with smooth gradients shows them best.
8. **Leave the dial on movie**, connect USB and run `windows/dump_info.cmd` again. This dump reads the numbers the camera's scaler is actually using.
9. To return to stock: battery out for 10 seconds. (`open_gate_putback.cmd` does the same in three steps without a power cut.)

**If the camera restarts by itself** at any point: do not pull the battery. Turn the dial to stills, connect USB, run `windows/dump_info.cmd`, and only then pull the battery for 10 seconds. The camera's own log of the fault survives a restart but not a battery pull.

**Please send back**

- The zipped `windows/camera_private` folder.
- The patched clip as the camera wrote it (the original file, not a re-encode or a screenshot).
- What you saw, in standby and while recording: a normal picture, a squeezed one, a cropped one, stepped tones, flicker, a restart, a freeze, and after how many seconds.
- Your settings: file format and record setting (bit depth), frame rate, NTSC or PAL, SteadyShot, lens compensation, and whether any of them changed since your last test.

**For judging the framing** (the first test recorded 3840 × 2560, but which part of the sensor it holds is not settled): from a tripod, same lens, focus and scene, please also send a stills photo (the full 3:2 sensor area) and a few seconds of stock 4K 24p recorded after a battery pull. Comparing the patched clip with another video mode while the patch is applied does not work: the patch changes sensor settings that the other 4K modes share.

**If the camera misbehaves** (grey lines, flicker, restart, freeze, recording that stops by itself): do not pull the battery straight away if the camera still responds. Turn the dial to stills, connect USB, run `dump_info.cmd`, and send the folder: the camera's own log of what went wrong is lost with the battery pull. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery.

**If the apply stops part-way:** it says at which step. Pull the battery for 10 seconds to be sure of the camera's state, and send the folder.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *the camera is in service mode but that device has no libusb driver yet*: expected on the first run. Do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 5.01 update*: another firmware or model. Nothing further is sent.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug, and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/` (the scripts, the pinned program files, their source, and the three patch designs).
- `PORT_NOTES.md`: how the A7 IV patch maps onto the A7S III, what is verified and what is not.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
