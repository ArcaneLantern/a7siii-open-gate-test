"""A7S III (ILCE-7SM3) firmware 5.01: apply, or put back, the open-gate state in the camera's MEMORY.

  python s3_apply.py apply    [--no-screen] [--no-meta] [--dry-run]
  python s3_apply.py putback  [--no-screen] [--dry-run]
  python s3_apply.py screen | screen-putback  [--dry-run]
  python s3_apply.py apply4224   [--no-screen] [--no-meta | --rate300] [--dry-run]     the 4224x2816 state (NOT RUN ON A CAMERA YET)
  python s3_apply.py putback4224 [--no-screen] [--rate300] [--dry-run]
  python s3_apply.py realrows | realrows-putback [--no-screen] [--no-meta] [--dry-run]  its first half alone, into the proven 3840x2560 file
  (the apply forms and screen take --no-movie-session to leave out the closing read-only session)

THE DEFAULT STATE OF THE A7S III (the owner, 2026-11-23): open gate with the screen steps. On one tester's camera
(2026-11-22) it records a true 3840x2560 file of the whole sensor area, the rear screen shows the picture at 3:2, and
C3 steps the preview. New in this kit: MP4 header height (3840x2560 in tkhd, stsd, PROF) in L19 v2, and a fourth C3 preview, 2.25:1 for 1.5x lenses.

  apply    five steps, each its own USB session: L5 sensor side (ogsq_s3_v5), L16 output size (outsz2560_s3_v1),
           L19 encoder side and MP4 header height (ogfile2560_hs_s_s3_v2), S16 rear screen and viewfinder at 3:2 with the focus frames
           (lcdratio32_s3_v1), C19 the C3 key steps the preview 3:2 -> 2:1 -> 2.25:1 -> 2.4:1 in movie mode
           (lcdcycle_s3_v3). Afterwards: XAVC HS 4K or XAVC S 4K at 23.98p only. With --no-screen only the first three.
           --no-meta: N19 (ogfile2560_hs_s_s3_v1) instead of L19, leaving MP4 headers at 3840x2160.
           A step that finds its bytes already applied says NOTHING TO DO and counts as passed.
  putback  the reverse: C20, S17, L20, L17, L6 (with --no-screen the last three). L20 also puts back an apply made with
           --no-meta. The screen part needs the preview at 3:2: press C3 until it is. A cold boot (battery out for 10 seconds) also undoes everything.
  screen / screen-putback   only the two screen steps (S16, C19) or their put back (C20, S17).

The MP4 header height (L19 v2, matching the A7 IV and ZV-E1): the file's tkhd, its stsd entry and Sony's PROF box say 3840x2560, so
editors open it at 3:2 without a remux (preserving Sony gyro metadata). Sony's XML (M01.XML beside the file, and the one inside it)
still says 3840x2160 16:9. Warm power-switch warning (Issue #3): switching the camera off and on without pulling the battery can leave
the main-processor encoder side (av-cam.bin and libmpr.so, including MP4 headers) applied while coprocessor sites reset to stock.
Pull the battery for 10 seconds to return everything to stock.

THE 4224x2816 STATE (2026-11-28, built and emulated, NOT RUN ON A CAMERA): the central 4224 x 2816 of the sensor's 4240 x 2832, pixel
for pixel (8 columns and 8 rows left out at each edge; a 4240-wide picture is refused by the camera's scaler, whose two units each need
a width that is a multiple of 32).
  apply4224  four steps, then the two screen steps: D16 output planes (dmm7slot_s3_v1: the planes of the 4K layout grow from
             13,271,040 to 14,942,208 bytes, as the FX6 kit's memory step), H5 sensor side with the first stage passed one to one
             (ogh2816_s3_v1: ogsq_s3_v5's sensor cells; front end 4240 x 2816; sampling ratio 27/32), K16 output size 4224 x 2816
             (outsz4224_s3_v1), K19 encoder side on both encoder cores and the MP4 header size (ogfile4224_s3_v1).
             --no-meta: J19 instead of K19 (the MP4 headers keep 3840x2160). --rate300: R19 instead of K19 (the 100M record
             settings record at 300 Mbps; use a V60 / V90 or CFexpress card).
  putback4224  the reverse: C20, S17, K20 (R20 with --rate300), K17, H6, D17.
  realrows   H5, L16, L19 and the screen steps: the new sensor side alone, with the proven 3840x2560 output size and encoder side.
             The file is 3840 x 2560 as in the default state, made from 4224 x 2816 real pixels at scale 1.1 both ways (the default
             state squeezes the rows to 2,392 first). It is the smaller test: only H5 is new in it. realrows-putback undoes it.
The three states share sites: put one back (or pull the battery for 10 seconds) before applying another. A step of one state on a
camera holding another writes nothing and says so.

Rules it keeps:
- It starts only if the newest saved read-only check of this kit (s3read_v9) says VERDICT READY.
- It stops at the first step that does not end in DONE or NOTHING TO DO, and says what state that leaves.
- Each step is one pinned library; the runner (s3_run.py) refuses any other bytes.
Nothing is written to a firmware file or to the camera's settings. What is written lives in the running camera's
memory. A cold boot (battery out for 10 seconds) removes it. Keep the camera switched on from the first step to the last.
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
STEPS = {"apply": ("L5", "L16", "L19"), "putback": ("L20", "L17", "L6"), "screen": ("S16", "C19"), "screen-putback": ("C20", "S17"),
         # the 4224x2816 state (memory first, as the FX6 kit) and its first half alone into the 3840x2560 file
         "apply4224": ("D16", "H5", "K16", "K19"), "putback4224": ("K20", "K17", "H6", "D17"),
         "realrows": ("H5", "L16", "L19"), "realrows-putback": ("L20", "L17", "H6")}
APPLIES = {"apply": "putback", "apply4224": "putback4224", "realrows": "realrows-putback"}     # the open-gate states and their put backs
FIT_4224 = s3_run.FIT_4224
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
    """The newest saved read-only check or dump that fetched a result: (folder name, ready?) or None. A session that stopped
    before the camera answered is skipped. Only s3read_v9 results count; both a stock preflight and a coherent applied
    closing dump (with or without --no-meta, --no-screen, or runtime stored_record) report ready, while mixed/partial states do not."""
    for folder, man in sessions():
        res = man.get("results", {})
        f = (res.get("ct6", {}).get("result") or {}).get("s3")
        if res.get("which") in ("check", "dump") and f:       # a dump makes every check the check makes, and gives the same verdict
            current = f.get("header") == "s3read s3read_v9 %s for ILCE-7SM3 5.01; read-only" % res["which"]
            return folder.name, current and f.get("ready") is True and not f.get("identity_differs")
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


def movie_session(what="apply"):
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
    if what in ("apply4224", "realrows"):
        blk = ((((f.get("decoded") or {}).get("scaler_state") or {}).get("second_scaler_block_0x140043c")) or {}).get("words")
        say("The second scaler's block reads %s; this state as designed: %s (4224 x 2816 from column 8, scale %s)."
            % (blk, FIT_4224, "1" if what == "apply4224" else "1.1 into 3840 x 2560"))
        say("NOT READY in the lines above is expected here: this read-only helper compares with the default state's bytes.")
        say("Each step of the apply checked its own bytes. Before another apply: battery out for 10 seconds, then check_readonly.")
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
    ap.add_argument("--no-screen", action="store_true", help="with the apply or the put back of a state: only the open-gate steps, without the two screen steps")
    ap.add_argument("--no-meta", action="store_true", help="with apply or realrows: the encoder step without the MP4 header height (N19); with apply4224: without the MP4 header size (J19). The headers say 3840x2160 as before")
    ap.add_argument("--rate300", action="store_true", help="with apply4224 or putback4224: the encoder step R19 / R20, whose 100M record settings record at 300 Mbps")
    ap.add_argument("--screen", action="store_true", help="accepted and ignored: the screen steps are part of apply and putback now")
    ap.add_argument("--no-movie-session", action="store_true", help="with apply or screen: leave out the closing read-only session with the dial on movie")
    a = ap.parse_args()
    steps = STEPS[a.what]
    state = a.what in APPLIES or a.what in APPLIES.values()          # an open-gate state or its put back (not the screen steps alone)
    if a.no_screen and not state:
        raise SystemExit("--no-screen goes with the apply or the put back of a state. Nothing was sent.")
    if a.no_meta and a.what not in APPLIES:
        raise SystemExit("--no-meta goes with apply, apply4224 or realrows (the put back's L20 / K20 puts back either encoder step). Nothing was sent.")
    if a.rate300 and (a.what not in ("apply4224", "putback4224") or a.no_meta):
        raise SystemExit("--rate300 goes with apply4224 or putback4224, and not with --no-meta. Nothing was sent.")
    with_screen = not a.no_screen
    if state and with_screen:
        steps = steps + STEPS["screen"] if a.what in APPLIES else STEPS["screen-putback"] + steps
    if a.no_meta:
        steps = tuple({"L19": "N19", "K19": "J19"}.get(k, k) for k in steps)
    if a.rate300:
        steps = tuple({"K19": "R19", "K20": "R20"}.get(k, k) for k in steps)
    applying = a.what in APPLIES or a.what == "screen"
    new_state = a.what in ("apply4224", "realrows")
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
    if a.what == "apply4224":
        say("THE 4224x2816 STATE HAS NOT RUN ON A CAMERA YET. Its sensor cells are those of the state that records on an A7S III; new here:")
        say("  the output planes (D16; the same words ran on an FX6), the first stage passed one to one (H5), the output size (K16) and the")
        say("  encoder side on both encoder cores (%s). If the camera stops, restarts or shows no picture: that is a result too; see below."
            % ("R19, 300 Mbps" if a.rate300 else "J19" if a.no_meta else "K19"))
    elif a.what == "realrows":
        say("THIS TEST HAS NOT RUN ON A CAMERA YET. Only its first step (H5) is new: the output size and the encoder side are the default state's.")
    if applying:
        if not new_state:
            say("The open-gate steps and the screen steps have worked on one A7S III (2026-11-22)." if a.what == "apply" else "This adds the two screen steps to an applied open-gate state.")
        if with_screen:
            say("New in this kit, not run on a camera yet: a fourth C3 preview, 2.25:1 for 1.5x lenses (the C3 step is a new build).")
            say("If screen steps of an earlier kit are still in the camera's memory: switch the camera off and on, or pull the battery, first.")
    else:
        say("It has to follow an apply of this kit.")
    say("A cold boot (battery out for 10 seconds) returns the camera to stock. A warm power switch (without pulling the battery) can leave")
    say("the encoder side applied while coprocessor sites reset to stock (Issue #3): so pull the battery for 10 seconds before starting, and")
    say("KEEP THE CAMERA SWITCHED ON from now until the script says it is finished.")
    if a.what in APPLIES:
        say("Before you go on: dial on stills, a charged battery, and a camera that was cold booted and has not been in movie mode since.")
        say("(If this state is already applied in this power-on, its steps will say NOTHING TO DO: that is fine. If ANOTHER open-gate state is")
        say(" applied, the first step that meets it stops and writes nothing: put that state back, or pull the battery for 10 seconds, first.)")
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
            if new_state:
                say("(To undo the steps that passed without a cold boot: s3_apply.py %s; a step with nothing to undo says NOTHING TO DO.)" % APPLIES[a.what])
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
            movie_session(a.what)
        say()
        say("Use only XAVC HS 4K or XAVC S 4K at 24p (23.98p) while it is applied: 60p distorted the picture and crashed the tester's camera.")
        if "L19" in steps:
            say("The MP4 headers say 3840x2560 (editors open the file at 3:2 without a remux, keeping Sony gyro metadata); Sony's XML still says 3840x2160 16:9.")
        if a.what == "apply4224":
            say("THE 4224x2816 STATE. Record a few seconds in XAVC HS 4K at 24p first, stop, and check that the clip plays on a computer; then XAVC S 4K.")
            say("  Expected: a 4224 x 2816 file, the central 4224 x 2816 of the sensor pixel for pixel, at the record setting's bit rate%s."
                % (" (300 Mbps on the 100M settings)" if a.rate300 else ""))
            say("  The MP4 headers %s. The camera will probably not play the clip itself."
                % ("keep 3840x2160: MediaInfo shows the stream's 4224x2816" if a.no_meta else "say 4224x2816 (3:2); Sony's XML still says 3840x2160 16:9"))
            say("  Please report: does it record and stop by itself; the clip (or MediaInfo's text); whether some frames have a band of wrong rows at the")
            say("  top or bottom (about 300 rows: a plane of the old size still in use; go to stills and back to movie, or record again, and say if it goes);")
            say("  the live view; anything the camera says. And send camera_private.")
        elif a.what == "realrows":
            say("THE REAL-ROWS TEST. Record a few seconds in XAVC HS 4K at 24p. Expected: a 3840 x 2560 file as in the default state, a little")
            say("  sharper down the frame (2,816 real rows where the default state has 2,392), with 8 sensor columns and rows left out at each edge.")
            say("  Please report: does it record; the clip; the live view; and send camera_private. If this works, apply4224 is the next test.")
        say("If the camera stops or restarts: do NOT pull the battery yet. Dial to stills, replug USB and run dump_info, then send camera_private.")
        say("To return to stock: battery out for 10 seconds (a warm power switch alone can leave the encoder side / MP4 headers applied — Issue #3).")


if __name__ == "__main__":
    main()
