"""A7S III (ILCE-7SM3) firmware 5.01: apply, or put back, the open-gate state in the camera's MEMORY.

  python s3_apply.py apply    [--no-screen] [--dry-run]
  python s3_apply.py putback  [--no-screen] [--dry-run]
  python s3_apply.py screen | screen-putback  [--dry-run]
  (apply and screen take --no-movie-session to leave out the closing read-only session)

THE DEFAULT STATE OF THE A7S III (the owner, 2026-11-23): open gate with the screen steps. On one tester's camera
(2026-11-22) it records a true 3840x2560 file of the whole sensor area, the rear screen shows the picture at 3:2, and
C3 steps the preview. New in this kit and not run yet: a fourth C3 preview, 2.25:1 for 1.5x lenses.

  apply    five steps, each its own USB session: L5 sensor side (ogsq_s3_v5), L16 output size (outsz2560_s3_v1),
           L19 encoder side (ogfile2560_hs_s_s3_v1), S16 rear screen and viewfinder at 3:2 with the focus frames
           (lcdratio32_s3_v1), C19 the C3 key steps the preview 3:2 -> 2:1 -> 2.25:1 -> 2.4:1 in movie mode
           (lcdcycle_s3_v3). Afterwards: XAVC HS 4K or XAVC S 4K at 23.98p only. With --no-screen only the first three.
           A step that finds its bytes already applied says NOTHING TO DO and counts as passed.
  putback  the reverse: C20, S17, L20, L17, L6 (with --no-screen the last three). The screen part needs the preview
           at 3:2: press C3 until it is. A cold boot (battery out for 10 seconds) also undoes everything.
  screen / screen-putback   only the two screen steps (S16, C19) or their put back (C20, S17).

The closing session (apply and screen). After the steps, the live view is glitchy (purple, lower part black) whenever
movie mode is entered from stills; a read-only dump session taken with the dial on movie, or the start of a recording,
corrects it until the next switch from stills (the tester, 2026-11-22). So the script ends by asking for the dial on
MOVIE and an unplug and replug, and runs the read-only dump itself. Nothing is written in that session.

Rules it keeps:
- It starts only if the newest saved read-only check of this kit says VERDICT READY.
- It stops at the first step that does not end in DONE or NOTHING TO DO, and says what state that leaves.
- Each step is one pinned library; the runner (s3_run.py) refuses any other bytes.
Nothing is written to a firmware file or to the camera's settings. What is written lives in the running camera's
memory. A cold boot (battery out for 10 seconds) removes it. On the tester's A7S III switching the camera off and on with
the power switch removed it as well (reported 2026-11-22; on the A7 IV it does not), so the camera must stay on from the
first step to the last.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CT1_usb_first_contact"))
sys.path.insert(0, str(HERE))
import ct1_common as c  # noqa: E402
import s3_run  # noqa: E402

FIRMWARE = s3_run.FIRMWARE
STEPS = {"apply": ("L5", "L16", "L19"), "putback": ("L20", "L17", "L6"), "screen": ("S16", "C19"), "screen-putback": ("C20", "S17")}
RUNNER = HERE / "s3_run.py"
LISTER = HERE.parent / "CT1_usb_first_contact" / "ct1_stage2_service.py"


def say(text=""):
    print(text, flush=True)


def sessions():
    """Saved sessions of this kit, newest first: (folder, manifest)."""
    root = c.PRIVATE_ROOT
    out = []
    if root.is_dir():
        for folder in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("CT6_")), reverse=True):
            try:
                out.append((folder, json.loads((folder / "manifest.json").read_text(encoding="utf8"))))
            except (OSError, ValueError):
                continue
    return out


def last_check():
    """The newest saved read-only check that fetched a result: (folder name, ready?) or None. A check that stopped before the camera
    answered (no driver yet, no camera seen, an old result on the RAM disk: all seen on the first A7S III run) says nothing and is skipped.
    A result of the first helper build (s3read_v1) is not accepted: its verdict was wrong on a stock camera."""
    for folder, man in sessions():
        res = man.get("results", {})
        f = (res.get("ct6", {}).get("result") or {}).get("s3")
        if res.get("which") in ("check", "dump") and f:       # a dump makes every check the check makes, and gives the same verdict
            current = any(v in f.get("header", "") for v in ("s3read_v2 ", "s3read_v3 ", "s3read_v4 ", "s3read_v5 ", "s3read_v6 ", "s3read_v7 ", "s3read_v8 "))
            return folder.name, current and bool(f.get("ready")) and not f.get("identity_differs")
    return None


def last_result_sha():
    """The SHA-256 of the result the newest session fetched: the runner deletes a result left on the RAM disk only if it has this hash."""
    for _, man in sessions():
        try:
            return man["results"]["ct6"]["result"]["sha256"]
        except (KeyError, TypeError):
            continue
    return None


def usb_state():
    r = subprocess.run([sys.executable, "-I", "-B", str(LISTER), "--list"], capture_output=True, text=True, encoding="utf8", errors="replace", cwd=str(LISTER.parent))
    import re
    m = re.search(r"libusb sees: (\d+) Sony mass-storage device\(s\).*?, (\d+) Sony service device\(s\)", r.stdout)
    if not m:
        return "other"
    return "drive" if int(m.group(1)) == 1 and int(m.group(2)) == 0 else "service" if int(m.group(2)) else "other"


def wait_for_drive(first, timeout=600):
    asked, end = False, time.time() + timeout
    while usb_state() != "drive":
        if not asked:
            say()
            if first:
                say("The camera is not showing as a USB drive. Turn it on, dial on stills, connect USB (USB Connection Mode: Mass Storage).")
            else:
                say(">>> Unplug the USB cable from the camera and plug it in again.")
                say(">>> Do NOT power the camera off or pull the battery: that would leave the steps half done.")
            say("Waiting for the camera (Ctrl+C to stop) ...")
            asked = True
        if time.time() > end:
            return False
        time.sleep(2)
    return True


def wait_for_replug(timeout=900):
    """Wait until the camera has been unplugged and shows up as a USB drive again. False on timeout."""
    end = time.time() + timeout
    while usb_state() != "other":                    # still plugged in, as a drive or in service mode
        if time.time() > end:
            return False
        time.sleep(1)
    while usb_state() != "drive":
        if time.time() > end:
            return False
        time.sleep(2)
    return True


def movie_session():
    """The closing read-only session, taken with the dial on movie: the camera starts its picture in movie mode when it ends."""
    say()
    say("=" * 78)
    say("One more session, and it only READS. It is what corrected the glitchy live view after the apply in every test so far.")
    say(">>> 1. Turn the mode dial to MOVIE (File Format XAVC HS 4K or XAVC S 4K, 24p).")
    say(">>> 2. Unplug the USB cable. Look at the rear screen for five seconds and remember it: right, or glitchy?")
    say(">>> 3. Plug the USB cable in again.")
    say(">>> Do NOT switch the camera off: on this camera the power switch removes the patch.")
    say("Waiting for the unplug and the replug (Ctrl+C to stop; the patch stays applied either way) ...")
    if not wait_for_replug():
        say("The camera did not come back as a USB drive. The steps are applied all the same.")
        say("If the live view is glitchy: start and stop a short recording, or run dump_info with the dial on movie.")
        return
    cmd = [sys.executable, "-I", "-B", str(RUNNER), "dump", "--go", "--firmware-shown", FIRMWARE]
    clear = last_result_sha()
    if clear:
        cmd += ["--clear-result", clear]
    rc = subprocess.run(cmd).returncode
    which, f = step_outcome()
    say()
    if rc or which != "dump" or not f:
        say("The read-only session did not finish. The steps are applied all the same.")
        say("If the live view is glitchy: start and stop a short recording, or run dump_info with the dial on movie.")
        return
    column = ((f.get("decoded") or {}).get("sensor_registers") or {}).get("closest_column")
    if column != 1:                                  # the open-gate 4K 24p mode runs sensor register column 1
        say("NOTE: before this session the sensor was not in the open-gate 4K 24p mode (register column %s, not 1)." % column)
        say("      Was the dial on movie, at 4K 24p? If not: set it, replug, and run dump_info once more.")
    say(">>> Unplug USB now. The live view should be right.")
    say("    Whenever you come back to movie mode from stills it is glitchy again (purple, lower part black): start and stop a")
    say("    short recording, and it is right until the next visit to stills. We have not found the cause of this yet.")


def step_outcome():
    for _, man in sessions():
        f = man.get("results", {}).get("ct6", {}).get("result", {}).get("s3")
        return (man.get("results", {}).get("which"), f) if f else (None, None)
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=sorted(STEPS))
    ap.add_argument("--dry-run", action="store_true", help="show the steps and what each would send; nothing is sent")
    ap.add_argument("--no-screen", action="store_true", help="with apply or putback: only the three open-gate steps, without the two screen steps")
    ap.add_argument("--screen", action="store_true", help="accepted and ignored: the screen steps are part of apply and putback now")
    ap.add_argument("--no-movie-session", action="store_true", help="with apply or screen: leave out the closing read-only session with the dial on movie")
    a = ap.parse_args()
    steps = STEPS[a.what]
    if a.no_screen and a.what not in ("apply", "putback"):
        raise SystemExit("--no-screen goes with apply or putback. Nothing was sent.")
    with_screen = not a.no_screen
    if a.what in ("apply", "putback") and with_screen:
        steps = steps + STEPS["screen"] if a.what == "apply" else STEPS["screen-putback"] + steps
    applying = a.what in ("apply", "screen")
    for k in steps:                                  # every library must be the pinned one before anything starts
        name, sha, _ = s3_run.WRITE_STEPS[k]
        p = s3_run.S3 / name
        if not p.is_file() or c.sha256(p.read_bytes()) != sha:
            raise SystemExit("%s is missing or is not the pinned build. Nothing was sent." % name)
    say("A7S III 5.01, %s: %d steps" % (a.what, len(steps)))
    for n, k in enumerate(steps, 1):
        say("  %d. %s  %s  (library %s...)" % (n, k, s3_run.WRITE_STEPS[k][2], s3_run.WRITE_STEPS[k][1][:16]))
    if applying and not a.no_movie_session:
        say("  then one read-only session (dump) with the dial on movie: it corrects the glitchy live view after the apply. Nothing is written in it.")
    if a.dry_run:
        for k in steps:
            say()
            say("--- %s, what the session would send:" % k)
            r = subprocess.run([sys.executable, "-I", "-B", str(RUNNER), k, "--dry-run"], capture_output=True, text=True, encoding="utf8", errors="replace")
            say(r.stdout.rstrip() or r.stderr.rstrip())
        say()
        say("Dry run only: nothing was sent to any device.")
        return
    chk = last_check()
    if applying and (chk is None or not chk[1]):
        raise SystemExit("The newest saved read-only check %s. Run the check first and get VERDICT READY. Nothing was sent."
                         % ("does not exist" if chk is None else "(%s) does not say READY" % chk[0]))
    say()
    say("This WRITES into the running camera's memory (not its firmware, not its settings).")
    if applying:
        say("The open-gate steps and the screen steps have worked on one A7S III (2026-11-22)." if a.what == "apply" else "This adds the two screen steps to an applied open-gate state.")
        if with_screen:
            say("New in this kit, not run on a camera yet: a fourth C3 preview, 2.25:1 for 1.5x lenses (the C3 step is a new build).")
            say("If screen steps of an earlier kit are still in the camera's memory: switch the camera off and on, or pull the battery, first.")
    else:
        say("It has to follow an apply of this kit.")
    say("A cold boot (battery out for 10 seconds) returns the camera to stock. On the tester's camera the power switch did too:")
    say("so KEEP THE CAMERA SWITCHED ON from now until the script says it is finished.")
    if a.what == "apply":
        say("Before you go on: dial on stills, a charged battery, and a camera that was cold booted and has not been in movie mode since.")
        say("(If the open-gate state is already applied in this power-on, its three steps will say NOTHING TO DO: that is fine.)")
    else:
        say("Before you go on: a charged battery." + (" Press C3 until the rear screen is back at 3:2." if a.what != "screen" and with_screen else ""))
    if input("Firmware version in the camera's menu: ").strip() != FIRMWARE:
        raise SystemExit("Not %s. Nothing was sent." % FIRMWARE)
    if input("Type YES to write to the camera's memory: ").strip() != "YES":
        raise SystemExit("Not confirmed. Nothing was sent.")
    for n, k in enumerate(steps, 1):
        if not wait_for_drive(n == 1):
            raise SystemExit("The camera did not show up as a USB drive. Stopped before step %d (%s)." % (n, k))
        say()
        say("=" * 78)
        say("Step %d of %d: %s, %s" % (n, len(steps), k, s3_run.WRITE_STEPS[k][2]))
        cmd = [sys.executable, "-I", "-B", str(RUNNER), k, "--go", "--writes-memory", "--firmware-shown", FIRMWARE]
        clear = last_result_sha()
        if clear:
            cmd += ["--clear-result", clear]
        rc = subprocess.run(cmd).returncode
        which, f = step_outcome()
        if rc or which != k or not f or not f.get("ok"):
            say()
            say("STOPPED at step %d (%s): %s" % (n, k, "the session did not finish" if rc or which != k or not f else "outcome " + f["outcome"]))
            say("Steps before it are %s. To be sure of the camera's state: cold boot it (battery out for 10 seconds)." % ("applied" if applying else "put back"))
            say("Please send the newest folders in camera_private.")
            raise SystemExit(1)
    say()
    say("All %d steps passed (%s)." % (len(steps), a.what))
    if with_screen and applying:
        say("The screen steps: in movie mode the rear screen and the viewfinder should now show the whole picture at 3:2,")
        say("  with thin black bars above and below (the screen is 4:3). A circle should look round.")
        say("  C3 in movie mode steps the preview: 3:2 -> 2:1 (1.33x) -> 2.25:1 (1.5x) -> 2.4:1 (1.6x) -> 3:2. The file does not change.")
        say("  While they are applied C3 does nothing else in movie mode, and every 16:9 picture is shown at the chosen shape (other movie formats look squeezed).")
        say("  Please report: the screen in each of the three modes, the focus frames in each, the viewfinder, and anything C3 does that is not this.")
        say("  The closing session below saves a dump that reads the display tables: leave the preview at 3:2 for it.")
    if applying:
        if a.no_movie_session:
            say(">>> BEFORE you unplug: turn the mode dial to MOVIE. Then unplug USB.")
            say("    If the live view is glitchy: start and stop a short recording, or run dump_info with the dial on movie.")
        else:
            movie_session()
        say()
        say("Use only XAVC HS 4K or XAVC S 4K at 24p (23.98p) while it is applied: 60p distorted the picture and crashed the tester's camera.")
        say("If the camera stops or restarts: do NOT pull the battery yet. Dial to stills, replug USB and run dump_info, then send camera_private.")
        say("To return to stock: battery out for 10 seconds. (Switching off and on did it too on the tester's camera.)")


if __name__ == "__main__":
    main()
