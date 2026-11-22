# A7S III open gate: test kit (firmware 5.01)

<p><b>Open gate works on one tester's A7S III (2026-11-22):</b> a true 3840 × 2560 recording of the whole sensor area at 23.98p. The patch only writes to RAM; a battery pull returns the camera to stock. It has run on one camera so far.</p>

This kit ports the A7 IV open-gate patch (a7iv-open-gate-test) to the Sony A7S III (ILCE-7SM3). The goal is a true 3840 × 2560 (3:2) recording in XAVC HS 4K and XAVC S 4K at 23.98p, set in the camera's memory only and gone after a battery pull. On the tester's camera it is also gone after switching the camera off and on.

**Where it stands (2026-11-22):**

- **Sensor step v5, the one in this kit, works.** The tester's report: open gate works, no distorted picture at 24p, the colours are right, and the file holds the full sensor area. The clip is HEVC 3840 × 2560, 23.976 fps, 4:2:2 10-bit, 97.5 Mbit/s (XAVC HS 4K). Both dumps show every patch site applied and the sensor in its full-height mode.
- **Stay on 4K 24p while it is applied.** Switching to 60p distorted the picture and crashed the tester's camera. A battery pull clears it.
- **The rear screen shows the picture squeezed into 16:9.** The file is right. Two optional screen steps correct that (picture at 3:2, and a preview for anamorphic lenses on the C3 key). Their first version ran on 2026-11-22: **the C3 key works and the 2:1 and 2.4:1 previews are right, but the 3:2 state stayed at 16:9.** This kit has the corrected version, which has not run yet: see "The screen".
- **The live view is glitchy the first time movie mode is entered after the apply.** A read-only dump session with the dial on movie, or pressing record, corrects it, and after that it stays right, also when you go to a photo mode and back (the tester, 2026-11-22). The apply script now ends with that read-only session itself. The cause is not found.
- **The power switch removes the patch on this camera.** The tester reports that after switching off and on, without a battery pull, there is no open gate. So the camera has to stay on while the steps run, and the patch has to be applied again after every power-off. We would like one read-only check after a power-off to confirm that every part is gone: see "Please send back".
- Not reported yet: XAVC S 4K, autofocus and exposure behaviour, long recordings, a camera set to PAL.

How it got here:

- The two read-only steps have run on an A7S III. The camera's software and every place the patch touches were as predicted.
- The write step has run twice on an A7S III. All three steps applied, the camera stayed stable and recorded a 3840 × 2560 file, and a battery pull returned it to stock. **But the framing was wrong:** no extra height, and the width was cropped. The cause was found in the dump: the first version changed the picture records of a different video mode.
- Sensor step v2 fixed that and ran once. The camera's scaler then took the whole picture, as designed, and the raw-frame buffer had room. **But the sensor still delivered only the 16:9 band:** the lower sixth of the picture was black, blacks were purple, and there were line artefacts (also in other 4K modes while the patch was applied). On this sensor the vertical window belongs to the sensor's mode, and v2 had not changed the mode.
- Sensor step v3 gave 4K 24p the camera's own full-height sensor mode (the one it uses for fast full-frame stills read-out), with that mode's receiver settings and a new 23.976 fps frame timing. It ran on an A7S III. **In one recording the whole sensor area reached the file** (checked against a photo), with stepped tones in the picture and a wrong standby picture before the recording. **On later attempts the picture flickered as soon as movie mode was entered, and the camera froze and restarted.** A battery pull returned it to stock each time.
- We found an error of ours in v3: one value of the new frame timing was outside the range the camera's own timings use (see `PORT_NOTES.md`). It fits the flicker and the restart, but that it caused them is not shown.
- Sensor step v4 was v3 with that timing value corrected. It ran on an A7S III: **no flicker and no restart.** The dumps show the full-height sensor mode and the whole sensor area scaled to 3840 × 2560. Two faults remain from v3: stepped tones in the picture, and a wrong live view when movie mode is entered from stills (it came right at the camera's next start of the picture: after a USB session with the dial on movie, or when a recording started).
- For the stepped tones we found a mismatch of ours: the stock 4K mode reads the sensor over a 10-bit link, the full-height mode over a 12-bit one, and six words in each of the two picture records still described the 10-bit link (see `PORT_NOTES.md`). That this causes the steps is not shown.
- Sensor step v5 is v4 with those record words set for the 12-bit link, and nothing else changed. It ran on an A7S III on 2026-11-22 with the result at the top of this list. The live view fault of v4 is handled by a closing read-only session of the apply script: see "How to run it".
- **If you ran an earlier version: pull the battery for 10 seconds before anything else.** The old patch may still be in the camera's memory, and v5 will refuse to apply on top of it.

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 5.01 software the port was made from and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | The same, plus facts for the port: memory map, the camera's own logs, sensor register state, internal tables, the display tables | No |
| `open_gate_apply.cmd` | Applies the open-gate state, in three steps | **Yes: memory only** |
| `open_gate_putback.cmd` | Puts the three steps back | Yes: memory only |
| `open_gate_apply_screen.cmd` | The three open-gate steps plus two screen steps. **The screen steps are a corrected second version, not run yet** | **Yes: memory only** |
| `screen_putback.cmd` | Puts the two screen steps back | Yes: memory only |

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

**What we do not know yet.** Why the live view is wrong the first time movie mode is entered after the apply (the script's closing session corrects it). How exposure and autofocus behave. Whether XAVC S 4K records as well as XAVC HS 4K did. The sensor is read more slowly in this mode: expect more rolling shutter (about 26 ms top to bottom). A battery pull returned the camera to stock after every fault so far.

**While it is applied:** use only XAVC HS 4K or XAVC S 4K at 24p. **60p distorted the picture and crashed the tester's camera**; other formats, frame rates, S&Q and APS-C/Super 35 are likely to fail or hang too. The rear screen and viewfinder show the picture squeezed vertically into 16:9. The optional screen steps are meant to correct both (see "The screen"); their second version has not run yet. The recorded file is what counts.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K) and 24p. APS-C/Super 35 off, S&Q off.
2. Pull the battery for 10 seconds, put it back, switch on. **Dial on stills.** Do not go into movie mode yet.
3. Connect USB and run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
4. It runs three steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until the script says it is finished: either one removes what was applied.
5. After the three steps the script asks for one more session, which only reads. **Turn the dial to movie, unplug USB, look at the rear screen for five seconds (right, or glitchy?), and plug in again.** The script then runs the read-only dump by itself. This session is what corrected the glitchy first live view in every test.
6. When it says so, unplug. The live view should be right, and it should stay right when you go to a photo mode and back. If it is glitchy all the same, start and stop a short recording.
7. Record 20 to 30 seconds, stop, and play the clip back.
8. If you can: **leave the dial on movie**, connect USB and run `windows/dump_info.cmd` once more. This dump reads the numbers the camera's scaler used for the recording.
9. To return to stock: battery out for 10 seconds, or `open_gate_putback.cmd`. On the tester's camera switching off and on did it too.

**If the camera restarts by itself** at any point: do not pull the battery. Turn the dial to stills, connect USB, run `windows/dump_info.cmd`, and only then pull the battery for 10 seconds. The camera's own log of the fault survives a restart but not a battery pull.

**Please send back**

- The zipped `windows/camera_private` folder.
- The patched clip as the camera wrote it (the original file, not a re-encode or a screenshot).
- What you saw, in standby and while recording: a normal picture, a squeezed one, a cropped one, stepped tones, flicker, a restart, a freeze, and after how many seconds.
- Your settings: file format and record setting (bit depth), frame rate, NTSC or PAL, SteadyShot, lens compensation, and whether any of them changed since your last test.
- **One check after a power-off.** When you are done: switch the camera off and on with the power switch (no battery pull), dial on stills, run `windows/check_readonly.cmd`, and include that folder. It tells us whether the power switch removes every part of the patch or only the part that makes the picture.

**For judging the framing** (the first test recorded 3840 × 2560, but which part of the sensor it holds is not settled): from a tripod, same lens, focus and scene, please also send a stills photo (the full 3:2 sensor area) and a few seconds of stock 4K 24p recorded after a battery pull. Comparing the patched clip with another video mode while the patch is applied does not work: the patch changes sensor settings that the other 4K modes share.

**If the camera misbehaves** (grey lines, flicker, restart, freeze, recording that stops by itself): do not pull the battery straight away if the camera still responds. Turn the dial to stills, connect USB, run `dump_info.cmd`, and send the folder: the camera's own log of what went wrong is lost with the battery pull. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery.

**If the apply stops part-way:** it says at which step. Pull the battery for 10 seconds to be sure of the camera's state, and send the folder.

## The screen (optional; second version, not run yet)

With open gate applied, the rear screen and the viewfinder show the whole sensor area squeezed into the 16:9 movie frame. Two more steps correct that.

**What the first version showed (one A7S III, 2026-11-22).** The C3 key worked: it stepped the preview, and the 2:1 and 2.4:1 previews came out as designed. The 3:2 state did not: the screen stayed at 16:9. The first version was the A7 IV's, and the A7 IV's rear screen is a 3:2 panel. This camera's is a 4:3 one (the dump now reads the panel type as well), where a 16:9 picture always sits between black bars and one pair of numbers in the display code sets its height. The first version changed a word this camera never reads.

**What this version does**

- **Step 4, the picture at 3:2.** The height of a 16:9 picture on the screen goes from width × 9/16 to width × 2/3, and the focus frames are told where the picture now is. The whole sensor area is then shown at its true shape, with thin black bars above and below (the screen is 4:3). The viewfinder is a 4:3 panel too and follows.
- **Step 5, the C3 key.** In movie mode, each press steps the preview: **3:2** (normal lenses), **2:1** (1.33x anamorphic), **2.4:1** (1.6x anamorphic), and back to 3:2. Full width, bars above and below. The recorded file does not change.

On an 800 × 600 screen the three previews are 534, 400 and 332 rows high: 1.50, 2.00 and 2.41 to 1. Each height is worked out from the screen's width alone, so 2:1 and 2.4:1 are those shapes on the screen and not a share of the 16:9 frame.

**How to run it**

1. **Pull the battery for 10 seconds first** if the first screen steps were applied since the last battery pull. The new steps refuse to go on top of them.
2. Follow "How to run it" above, but start `windows/open_gate_apply_screen.cmd` in step 3. It runs five steps, with an unplug and replug between each.
3. When all five have passed, the script's closing read-only session follows as above (dial to movie, unplug, look, replug). **Do not press C3 before it has finished:** its dump reads the display tables and the panel types with the preview at 3:2.

**While they are applied**

- C3 does nothing else in movie mode. In stills and playback it is unchanged, whatever it is assigned to.
- Every 16:9 picture on the rear screen and in the viewfinder takes the chosen shape, so other movie formats look squeezed there. HDMI is not changed.

**Please tell us**

- What the rear screen shows in movie mode after the apply: the whole picture with thin bars above and below and the right shape (a circle looks round), or still 16:9.
- What each C3 press does, and whether the cycle comes back to 3:2 (not 16:9).
- Whether the focus frames and the tracking box are drawn in each of the three previews.
- What the viewfinder shows.
- The zipped `windows/camera_private` folder, as always.

**The glitchy live view: what the tester found (2026-11-22).** It appears the first time movie mode is entered after the apply. A `dump_info.cmd` run with the dial on movie, or pressing record, corrects it. After that it stays right, also after switching to a photo mode and back. The apply script therefore ends with that read-only session. The cause is not found: a dump cannot show it, because the sensor is asleep while the camera is in a USB session.

Two things would still help:

1. **What you saw in the five seconds between the unplug and the replug** of the closing session: was the live view right at once, or glitchy until the session had run?
2. **What the glitch looks like,** if you see it: a phone photo or short video of the rear screen (dark, purple, torn, frozen, part of the picture missing, flickering).

**To remove only the screen steps:** press C3 until the preview is back at 3:2, turn the dial to stills, and run `windows/screen_putback.cmd`. Or pull the battery, which removes everything.

**If the camera freezes or restarts on a C3 press:** pull the battery for 10 seconds, apply with `open_gate_apply.cmd` (three steps, no screen steps) and tell us.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *the camera is in service mode but that device has no libusb driver yet*: expected on the first run. Do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 5.01 update*: another firmware or model. Nothing further is sent.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug, and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/` (the scripts, the pinned program files, their source, the three patch designs, and the two screen designs with the C3 routine's source in `tools/modding/lcdcycle_s3`).
- `PORT_NOTES.md`: how the A7 IV patch maps onto the A7S III, what is verified and what is not.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
