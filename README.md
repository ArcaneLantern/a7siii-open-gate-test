# A7S III open gate: read-only test kit (firmware 5.01)

This kit is the first step of porting the A7 IV open-gate patch (a7iv-open-gate-test) to the Sony A7S III (ILCE-7SM3). The goal is a true 3840 × 2560 (3:2) recording in XAVC HS 4K and XAVC S 4K at 23.98p, set in the camera's memory only, gone after a battery pull.

**Nothing in this kit has run on an A7S III yet.** That is what it is for. It contains two steps and both only read:

| Step | What it does | What you get |
|---|---|---|
| `check_readonly` | Confirms the camera runs the 5.01 software the port was made from, and reads what every place the patch would change holds now | A verdict: READY or NOT READY |
| `dump_info` | The same, plus facts the port still needs: kernel memory map, the camera's own logs, the sensor register state, a few internal tables | A folder of files to send back |

The step that writes the patch is not in this kit. It will be added once the results of these two steps match what the port predicts.

## What the two steps do to the camera

- They switch the camera to its service mode over USB, the way the A7 IV kit does.
- They write one small program file to the camera's service partition, which the camera loads once. The script deletes that file again in the same session and checks that it is gone.
- The program only reads. It creates one file, its report, on the camera's RAM disk; the script fetches it. A battery pull clears the RAM disk.
- No setting, no firmware file and no memory of the running camera is changed. The program contains no code that could: it has no write towards the image processor and no writable memory mapping. Its source is in `windows/tools/camera_tests/CT6_memory_read_check/helper_s3/s3read.c`.

Risks you should still know about:
- The service route has only been used on the A7 IV. On the A7S III the commands may be refused. The script then stops and says so.
- If a session breaks half-way (cable pulled, camera hangs), the program file can stay on the service partition. It does not run by itself. Run the same step again with `--remove-only` after replugging, or tell us.
- Use a charged battery and do not record or play back while a step runs.

## Before you start

1. The camera's menu must show **Ver. 5.01** (Setup, Setup Option, Version). On any other version the check will say NOT READY: please do not go on, tell us the version instead.
2. Set **USB Connection Mode** to **Mass Storage** and, if asked on connection, choose **Image Transfer (MSC)**.
3. Dial on **stills** (photo), camera on, connected by USB.

## Windows

1. Install Python 3.10 or later from python.org (with the "py launcher").
2. Run `windows/setup.cmd` once.
3. Install the libusb-win32 driver for the camera with [Zadig](https://zadig.akeo.ie): Options, List All Devices, pick the camera, choose libusb-win32, Replace Driver. The first run switches the camera to service mode, where it shows up as a new device (054C:0336 on the A7 IV): install the driver for that one too, then run the step again.
4. Run `windows/check_readonly.cmd`. Type the firmware version the menu shows when asked.
5. Unplug and replug the USB cable. Run `windows/dump_info.cmd`.
6. For a second dump (very useful): pull the battery for ten seconds, start the camera, set File Format XAVC S 4K at 24p, turn the dial to movie and look at the picture for a few seconds, turn it back to stills, connect, and run `windows/dump_info.cmd` again.

Each run makes a new folder in `windows/camera_private`. **Zip the whole `camera_private` folder and send it back.** It holds the camera's report, a short summary (`s3_report.txt`) and the USB device ids your PC saw. It can contain your camera's serial number in the kernel log lines; nothing else personal.

To see what a step would send without sending anything: `check_readonly.cmd --dry-run`. To test the script against a simulated camera: `check_readonly.cmd --selftest`. (Both still ask for the version first; type 5.01.)

macOS and Android are not covered yet.

## If something stops

Every stop prints a reason and "Nothing was sent" or what was sent. Please send that text. Common ones:

- *DeviceInfo.xml is not the file of the 5.01 update*: another firmware or model. Nothing further is sent.
- *a result file is already on the RAM disk*: an earlier run's report is still there. Pull the battery for ten seconds and start again.
- *a libJit.so is already on the service partition*: see `--remove-only` above.

## What is in here

- `windows/`: the two launchers, `setup.cmd`, and `tools/` (the scripts, the two pinned program files, their source, and the three patch designs for review).
- `PORT_NOTES.md`: how the A7 IV patch maps onto the A7S III, what was verified offline and what only a camera can answer.

Built on [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (vendored under `windows/tools/third_party`, MIT licence).
