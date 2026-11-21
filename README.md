# A7S III open gate: test kit (firmware 5.01)

<p><b>The current write tests are UNTESTED</b> they only write to ram, so should remove themselves and return the camera to stock with a battery pull, but they are again, not tested yet.</p?

This kit ports the A7 IV open-gate patch (a7iv-open-gate-test) to the Sony A7S III (ILCE-7SM3). The goal is a true 3840 × 2560 (3:2) recording in XAVC HS 4K and XAVC S 4K at 23.98p, set in the camera's memory only and gone after a battery pull.

**Where it stands (2026-11-22):**

- The two read-only steps have run on an A7S III. The camera's software and every place the patch touches were as predicted.
- **The write step has never run on any A7S III.** It is in this kit for a first test. It may give a wrong picture, or make the camera restart. Read "The write step" below before you run it.

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

**What we do not know yet.** Whether the sensor then reads its full height, whether the camera's raw-frame buffer has room for it, and whether the picture comes out whole. On the A7 IV the same kind of mistake showed as grey lines and a restart of the camera; a battery pull returned it to stock every time.

**While it is applied:** use only XAVC HS 4K or XAVC S 4K at 24p. Other formats, frame rates, S&Q and APS-C/Super 35 are likely to fail or hang. The rear screen and viewfinder will probably look squeezed vertically: the screen picture is not corrected on this camera yet. The recorded file is what counts.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K) and 24p. APS-C/Super 35 off, S&Q off.
2. Pull the battery for 10 seconds, put it back, switch on. **Dial on stills.** Do not go into movie mode yet.
3. Connect USB and run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
4. It runs three steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until it says all three steps passed.
5. Unplug USB. Turn the dial to movie. Look at the picture. Record 5 to 10 seconds, stop, and play the clip back.
6. **Leave the dial on movie**, connect USB and run `windows/dump_info.cmd`. With the patch applied, this dump reads the numbers the camera's scaler is actually using, which is what tells us whether the full sensor area reaches the file.
7. To return to stock: battery out for 10 seconds. (`open_gate_putback.cmd` does the same in three steps without a power cut.)

**Please send back**

- The zipped `windows/camera_private` folder.
- The patched clip.
- What you saw: a normal picture, a squeezed one, a cropped one, grey lines, a restart, a freeze.

**For judging the framing** (the first test recorded 3840 × 2560, but which part of the sensor it holds is not settled): from a tripod, same lens, focus and scene, please also send a stills photo (the full 3:2 sensor area) and a few seconds of stock 4K 24p recorded after a battery pull. Comparing the patched clip with another video mode while the patch is applied does not work: the patch changes sensor settings that the other 4K modes share.

**If the camera misbehaves** (grey lines, restart, freeze, recording that stops by itself): do not pull the battery straight away if the camera still responds. Connect USB, run `dump_info.cmd`, and send the folder: the camera's own log of what went wrong is lost with the battery pull. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery.

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
