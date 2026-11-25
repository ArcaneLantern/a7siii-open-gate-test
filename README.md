# A7S III open gate: test kit (firmware 5.01)

<p><b>Open gate works on one tester's A7S III (2026-11-22):</b> a true 3840 × 2560 recording of the whole sensor area at 23.98p, with the rear screen at 3:2 and an anamorphic preview on the C3 key. The patch only writes to RAM. It has run on one camera so far.</p>

This kit ports the A7 IV open-gate patch (a7iv-open-gate-test) to the Sony A7S III (ILCE-7SM3): a true 3840 × 2560 (3:2) recording in XAVC HS 4K and XAVC S 4K at 23.98p, set in the camera's memory only. A battery pull removes it.

**MP4 headers (L19 v2, matching the A7 IV and ZV-E1): no remux needed.** The encoder step `L19` (`ogfile2560_hs_s_s3_v2`) now also sets the height in the MP4 headers (`tkhd`, the `stsd` sample entry `avc1`/`hvc1`, and Sony's `PROF` box) to `2560`, so editors open clips at 3:2 straight off the card while preserving Sony gyro metadata without an `ffmpeg` remux. Sony's own XML (`M01.XML` beside the clip and the XML inside it) still says 3840 × 2160, 16:9. `--no-meta` (`N19`, or the `open_gate_apply_no_meta` launcher) uses `ogfile2560_hs_s_s3_v1` to keep 3840 × 2160 headers. `L20` puts back either `v2` or `v1`.

**Preflight (`s3read_v9`) and warm power-switch gating (Issue #3):** The read-only check and dump now inspect both MP4 header instructions (`0x223cc4` and `0x223d10` in `libmpr.so`) alongside all 25 coprocessor sites, 4 `L1-comb` sites, and 101 `av-cam.bin` sites. `VERDICT READY (stock preflight)` requires pure stock state (with the existing runtime-filled exception for `stored_record`, `outsize`, and `outsize_guard*`); a coherent applied closing `dump` (with or without `--no-meta` and with runtime `stored_record`) reports `VERDICT READY (open gate applied)`. Mixed or partial states—including a warm power-switch state where coprocessor sites reset to stock while `av-cam.bin` / `libmpr.so` stay applied (Issue #3), a single MP4 header site applied, or partial coprocessor sites—report `VERDICT NOT READY`. Always pull the battery for 10 seconds to return fully to stock; `s3_apply.py` requires an `s3read_v9` check. Offline C and Python regression tests run with `python -m unittest discover -s tests -v`.

**Where it stands (2026-11-23):**

- **The file is right.** Open gate works, no distorted picture at 24p, the colours are right, and the file holds the full sensor area. The clip is HEVC 3840 × 2560, 23.976 fps, 4:2:2 10-bit, 97.5 Mbit/s (XAVC HS 4K).
- **The screen is right.** With the screen steps the movie live view is 3:2 instead of the squeezed 16:9, and C3 steps the preview. A dump read the panel types: the rear screen and the viewfinder are both 4:3 panels. The screen steps are part of the default apply now.
- **New in this kit, not run yet:** a fourth C3 preview, 2.25:1 for 1.5x anamorphic lenses.
- **One fault is left: the live view is glitchy whenever movie mode is entered from stills** (purple, lower part black). Starting and stopping a short recording corrects it until the next visit to stills. The recorded file was right in every test. The cause is not found.
- **Stay on 4K 24p while it is applied.** Switching to 60p distorted the picture and crashed the tester's camera.
- **The power switch removes the patch on this camera** (the tester's report). The camera has to stay on while the steps run, and the patch has to be applied again after every power-off. We would like one read-only check after a power-off to confirm that every part is gone: see "Please send back".
- Not reported yet: XAVC S 4K, autofocus and exposure behaviour, long recordings, a camera set to PAL.

How it got here:

- The two read-only steps have run on an A7S III. The camera's software and every place the patch touches were as predicted.
- The write step has run twice on an A7S III. All three steps applied, the camera stayed stable and recorded a 3840 × 2560 file, and a battery pull returned it to stock. **But the framing was wrong:** no extra height, and the width was cropped. The cause was found in the dump: the first version changed the picture records of a different video mode.
- Sensor step v2 fixed that and ran once. The camera's scaler then took the whole picture, as designed, and the raw-frame buffer had room. **But the sensor still delivered only the 16:9 band:** the lower sixth of the picture was black, blacks were purple, and there were line artefacts (also in other 4K modes while the patch was applied). On this sensor the vertical window belongs to the sensor's mode, and v2 had not changed the mode.
- Sensor step v3 gave 4K 24p the camera's own full-height sensor mode (the one it uses for fast full-frame stills read-out), with that mode's receiver settings and a new 23.976 fps frame timing. It ran on an A7S III. **In one recording the whole sensor area reached the file** (checked against a photo), with stepped tones in the picture and a wrong standby picture before the recording. **On later attempts the picture flickered as soon as movie mode was entered, and the camera froze and restarted.** A battery pull returned it to stock each time.
- We found an error of ours in v3: one value of the new frame timing was outside the range the camera's own timings use (see `PORT_NOTES.md`). It fits the flicker and the restart, but that it caused them is not shown.
- Sensor step v4 was v3 with that timing value corrected. It ran on an A7S III: **no flicker and no restart.** The dumps show the full-height sensor mode and the whole sensor area scaled to 3840 × 2560. Two faults remain from v3: stepped tones in the picture, and a wrong live view when movie mode is entered from stills (it came right at the camera's next start of the picture: after a USB session with the dial on movie, or when a recording started).
- For the stepped tones we found a mismatch of ours: the stock 4K mode reads the sensor over a 10-bit link, the full-height mode over a 12-bit one, and six words in each of the two picture records still described the 10-bit link (see `PORT_NOTES.md`). That this causes the steps is not shown.
- Sensor step v5 is v4 with those record words set for the 12-bit link, and nothing else changed. It ran on an A7S III on 2026-11-22 with the result at the top of this list. The live view fault of v4 is still there: see "The glitchy live view".
- The first screen steps were the A7 IV's and assumed its 3:2 rear screen. On this camera the C3 key worked but the 3:2 state stayed at 16:9: the rear screen is a 4:3 panel, where a 16:9 picture always sits between bars and one pair of numbers in the display code sets its height. The second version changes that pair, and ran on 2026-11-22: 3:2 works.
- **If you ran an earlier version: switch the camera off and on, or pull the battery for 10 seconds, before anything else.** An old patch still in the camera's memory makes the new steps refuse.

| Launcher | What it does | Writes to the camera? |
|---|---|---|
| `check_readonly.cmd` | Confirms the camera runs the 5.01 software the port was made from and reads what every patch site holds. Verdict READY / NOT READY | No |
| `dump_info.cmd` | The same, plus facts for the port: memory map, the camera's own logs, sensor register state, internal tables, the display tables | No |
| `open_gate_apply.cmd` | Applies the default state in five steps: open gate (with 3840 × 2560 MP4 headers), the screen at 3:2, the C3 preview. Ends with one read-only session | **Yes: memory only** |
| `open_gate_apply_no_meta.cmd` | Applies open gate without the MP4 header height (`N19`, headers stay 3840 × 2160), plus the screen at 3:2 and C3 preview | **Yes: memory only** |
| `open_gate_apply_no_screen.cmd` | Only the three open-gate steps (with 3840 × 2560 MP4 headers; accepts `--no-meta`) | **Yes: memory only** |
| `open_gate_putback.cmd` | Puts the five steps back (puts back either `L19` v2 or `N19` `--no-meta`) | Yes: memory only |
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

## macOS, once (new, not run on an A7S III yet)

The macOS kit is the A7 IV kit's macOS port, carried over unchanged apart from the launcher names. It runs the same scripts as Windows (`windows/tools`).

1. Python 3.9 or later: the one macOS offers with the Xcode Command Line Tools (run `xcode-select --install` in Terminal) works, or install it from python.org.
2. Double-click `macos/setup.command`. It sets up Python and the USB library the scripts use. No Homebrew and no driver are needed.
3. Each Windows launcher has a macOS twin with the same name: `macos/check_readonly.command`, `dump_info.command`, `open_gate_apply.command`, `open_gate_apply_no_meta.command`, `open_gate_apply_no_screen.command`, `open_gate_putback.command`, `screen_putback.command`. Everything below that says `.cmd` works the same with the `.command` file.

Each live run asks for your Mac password: macOS keeps its own driver on the camera's USB connection, and only an administrator can hand the camera over to the script. The script unmounts the camera's memory card first; it does not erase anything on it. The results go to the same `windows/camera_private` folder.

If macOS refuses to open a .command file ("unidentified developer" or "could not verify"), open System Settings > Privacy & Security, scroll down and click "Open Anyway". Or open Terminal, type `bash` and a space, drag the .command file into the window, and press Return.

## Android (new, not run on a camera yet)

`android/A7SIII-OpenGate.apk` runs this kit from a phone connected to the camera by USB-C (or an OTG adapter). It carries exactly the files in `windows/tools` of this commit and runs them unchanged; only the USB access, the dialogs and the folder for the results are the phone's.

1. Install the APK (allow installing from unknown sources). It installs beside the A7 IV app; they do not share anything on the phone.
2. Set the camera as for the PC (below), and also **USB Power Supply: Off**, or it charges from the phone.
3. **1. Read-only check** first: the apply starts only after a check on this phone said READY. Then **2. Apply to camera**. The "Screen steps" box chooses between the five-step apply (ticked) and the three open-gate steps only.
4. When Android asks to open *A7S III Open Gate* for the camera, tick **Always** and press OK. It comes up twice: once in Mass Storage, once in service mode.
5. When the log says **unplug and plug in again**, do that with the phone cable. Never switch the camera off.
6. **Stop waiting** ends a wait for the camera. It never interrupts a step that is talking to the camera.
7. Afterwards, **Export logs** writes a zip to `Download/A7SIII-OpenGate/` on the phone: send that zip back.

**Self-test** and **Dry run** need no camera and send nothing.

## The read-only steps

Each launcher asks for the firmware version the menu shows. Each run makes a new folder in `windows/camera_private`.

- **Check or dump in the stills state:** dial on stills, connect, run the launcher.
- **Dump of the 4K state:** set File Format XAVC S 4K (or XAVC HS 4K) at 24p, APS-C/Super 35 off, S&Q off, SteadyShot not on Active. Dial on movie, record a few seconds, stop. **Leave the dial on movie**, connect, run `dump_info.cmd`.

What they do to the camera: they switch it to service mode, write one small program file to the service partition, which the camera loads once, and delete that file again in the same session. The program only reads and creates one file, its report, on the camera's RAM disk. Its source is `windows/tools/camera_tests/CT6_memory_read_check/helper_s3/s3read.c`.

## The write step

**What it changes.** Five groups of bytes in the running camera's memory, one per step:

1. The sensor read-out and the two 4K picture records of the image processor: full sensor height instead of the 16:9 band.
2. One size word: 3840 × 2160 becomes 3840 × 2560.
3. The encoder's tables for XAVC HS 4K and XAVC S 4K at 23.98p and 25p.
4. The screen: the height of a 16:9 picture on the rear screen and in the viewfinder goes from width × 9/16 to width × 2/3, and the focus frames are told where the picture now is. The live view is a 16:9 frame holding the whole sensor area, so this shows it at its true 3:2 shape, with thin black bars above and below (both screens are 4:3).
5. The C3 key: a small routine in the camera's application. In movie mode each press steps the preview (see "The C3 preview").

Each step first checks that every byte it is about to change holds its stock value, writes, reads back, and undoes its own writes if anything does not match. `open_gate_apply_no_screen.cmd` runs only the first three.

**What we do not know yet.** Why the live view is glitchy when movie mode is entered from stills (see "The glitchy live view"). How exposure and autofocus behave. Whether XAVC S 4K records as well as XAVC HS 4K did. The sensor is read more slowly in this mode: expect more rolling shutter (about 26 ms top to bottom).

**While it is applied**

- Use only XAVC HS 4K or XAVC S 4K at 24p. **60p distorted the picture and crashed the tester's camera**; other formats, frame rates, S&Q and APS-C/Super 35 are likely to fail or hang too.
- C3 does nothing else in movie mode. In stills and playback it is unchanged, whatever it is assigned to.
- Every 16:9 picture on the rear screen and in the viewfinder takes the chosen shape, so other movie formats look squeezed there. HDMI is not changed.
- **Do not switch the camera off:** on the tester's camera the power switch removes the patch, and it has to be applied again.

**How to run it**

1. In the menu, set File Format XAVC S 4K (or XAVC HS 4K) and 24p. APS-C/Super 35 off, S&Q off.
2. Switch the camera off and on, or pull the battery for 10 seconds, so that nothing of an earlier kit is left. **Dial on stills.** Do not go into movie mode yet.
3. Connect USB and run `windows/open_gate_apply.cmd`. It starts only if your newest saved check or dump says READY. It asks for the firmware version and for a typed YES.
4. It runs five steps. Between steps it asks you to **unplug and replug the USB cable. Do not switch the camera off and do not pull the battery** until the script says it is finished: either one removes what was applied.
5. After the five steps the script asks for one more session, which only reads. **Turn the dial to movie, unplug USB, and plug in again.** The script then runs the read-only dump by itself. The live view is glitchy between the unplug and the replug; this session corrects it. **Do not press C3 before it has finished.**
6. When it says so, unplug. The live view should be right, at 3:2.
7. Record 20 to 30 seconds, stop, and play the clip back.
8. To return to stock: switch the camera off and on (on the tester's camera), battery out for 10 seconds, or `open_gate_putback.cmd` with the preview at 3:2.

**The C3 preview**

In movie mode, each press of C3 steps the preview on the rear screen and in the viewfinder. The recorded file does not change.

| Press | Preview | For | Rows of 600 |
|---|---|---|---|
| start | 3:2 | normal lenses | 534 |
| 1 | 2:1 | 1.33x anamorphic | 400 |
| 2 | 2.25:1 | 1.5x anamorphic (**new in this kit, not run yet**) | 354 |
| 3 | 2.4:1 | 1.6x anamorphic | 332 |
| 4 | 3:2 again | | |

Each height is worked out from the screen's width alone, so these are the shapes on the screen. 3:2, 2:1 and 2.4:1 have run on a camera. The 2.25:1 state is the same routine with one more entry in its tables.

**The glitchy live view**

What the tester found on 2026-11-22, with this kit's sensor step:

- When movie mode is entered from stills, the live view is glitchy: purple, with the lower part fully black.
- Starting a recording corrects it. So does a read-only dump session with the dial on movie, which is why the apply ends with one.
- It stays right until the next visit to stills. Coming back to movie it is glitchy again.

So for now: **after every return from stills to movie, start and stop a short recording.** The file itself was right in every test. The cause is not found. Our reading, not shown: the sensor does not take up its full-height mode on a live switch from the stills live view, and does when its picture is started afresh.

**If the camera restarts by itself** at any point: do not pull the battery. Turn the dial to stills, connect USB, run `windows/dump_info.cmd`, and only then pull the battery for 10 seconds.

**Please send back**

- The zipped `windows/camera_private` folder.
- What each C3 press shows, the 2.25:1 preview above all, and whether the focus frames and the tracking box are drawn in each preview.
- What the viewfinder shows.
- **One check after a power-off.** When you are done: switch the camera off and on with the power switch (no battery pull), dial on stills, run `windows/check_readonly.cmd`, and include that folder. It tells us whether the power switch removes every part of the patch or only the part that makes the picture.
- **Two things about the glitch, if you can:** a phone photo or short video of the rear screen while it is glitchy; and whether pressing the playback button and returning to shooting, instead of recording, also corrects it.
- Your settings, if any changed since your last test: file format and record setting, frame rate, NTSC or PAL, SteadyShot.

**If the camera misbehaves** (grey lines, flicker, restart, freeze, recording that stops by itself, a freeze on a C3 press): do not pull the battery straight away if the camera still responds. Turn the dial to stills, connect USB, run `dump_info.cmd`, and send the folder. Then pull the battery for 10 seconds. If the camera does not respond at all, just pull the battery. `open_gate_apply_no_screen.cmd` applies open gate without the screen steps.

**If the apply stops part-way:** it says at which step. Pull the battery for 10 seconds to be sure of the camera's state, and send the folder.

**To remove only the screen steps:** press C3 until the preview is back at 3:2, turn the dial to stills, and run `windows/screen_putback.cmd`.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *the camera is in service mode but that device has no libusb driver yet*: expected on the first run. Do the Zadig step for the new device and run again.
- *DeviceInfo.xml is not the file of the 5.01 update*: another firmware or model. Nothing further is sent.
- *a libJit.so is already on the service partition*: a session broke half-way. Replug, and run the same step with `--remove-only`.

## What is in here

- `windows/`: the launchers, `setup.cmd`, and `tools/` (the scripts, the pinned program files, their source, the five patch designs, and the C3 routine's source in `tools/modding/lcdcycle_s3`).
- `macos/`: `setup.command` and one `.command` launcher per Windows launcher; they run `windows/tools`.
- `android/A7SIII-OpenGate.apk`: the phone app, carrying `windows/tools` as published here.
- `PORT_NOTES.md`: how the A7 IV patch maps onto the A7S III, what is verified and what is not.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
