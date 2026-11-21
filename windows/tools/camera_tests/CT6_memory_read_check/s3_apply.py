"""A7S III (ILCE-7SM3) firmware 5.01: apply, or put back, the open-gate state in the camera's MEMORY.

  python s3_apply.py apply    [--dry-run]
  python s3_apply.py putback  [--dry-run]

NEVER RUN ON A CAMERA (2026-11-21). This is the write kit of the port; it is held back until the read-only steps
(s3_run.py check and dump) have run on an A7S III and their results match what the port predicts.

  apply    three steps, each its own USB session: L5 sensor side (ogsq_s3_v3), L16 output size (outsz2560_s3_v1),
           L19 encoder side (ogfile2560_hs_s_s3_v1). Afterwards: XAVC HS 4K or XAVC S 4K at 23.98p only.
  putback  the reverse, L20, L17, L6. A cold boot (battery out for 10 seconds) also undoes everything.

Rules it keeps:
- It starts only if the newest saved read-only check of this kit says VERDICT READY.
- It stops at the first step that does not end in DONE or NOTHING TO DO, and says what state that leaves.
- Each step is one pinned library; the runner (s3_run.py) refuses any other bytes.
Nothing is written to a firmware file or to the camera's settings. What is written lives in the running camera's
memory until a cold boot; switching the camera off and on does not clear it.
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
STEPS = {"apply": ("L5", "L16", "L19"), "putback": ("L20", "L17", "L6")}
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
            current = any(v in f.get("header", "") for v in ("s3read_v2 ", "s3read_v3 ", "s3read_v4 ", "s3read_v5 "))
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


def step_outcome():
    for _, man in sessions():
        f = man.get("results", {}).get("ct6", {}).get("result", {}).get("s3")
        return (man.get("results", {}).get("which"), f) if f else (None, None)
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=sorted(STEPS))
    ap.add_argument("--dry-run", action="store_true", help="show the steps and what each would send; nothing is sent")
    a = ap.parse_args()
    steps = STEPS[a.what]
    for k in steps:                                  # every library must be the pinned one before anything starts
        name, sha, _ = s3_run.WRITE_STEPS[k]
        p = s3_run.S3 / name
        if not p.is_file() or c.sha256(p.read_bytes()) != sha:
            raise SystemExit("%s is missing or is not the pinned build. Nothing was sent." % name)
    say("A7S III 5.01, %s: %d steps" % (a.what, len(steps)))
    for n, k in enumerate(steps, 1):
        say("  %d. %s  %s  (library %s...)" % (n, k, s3_run.WRITE_STEPS[k][2], s3_run.WRITE_STEPS[k][1][:16]))
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
    if a.what == "apply" and (chk is None or not chk[1]):
        raise SystemExit("The newest saved read-only check %s. Run the check first and get VERDICT READY. Nothing was sent."
                         % ("does not exist" if chk is None else "(%s) does not say READY" % chk[0]))
    say()
    say("This WRITES into the running camera's memory (not its firmware, not its settings).")
    say("It has %s. A cold boot (battery out for 10 seconds) returns the camera to stock." % ("never been run on an A7S III" if a.what == "apply" else "to follow an apply of this kit"))
    say("Before you go on: dial on stills, a charged battery, and for apply a camera that was cold booted and has not been in movie mode since.")
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
            say("Steps before it are %s. To be sure of the camera's state: cold boot it (battery out for 10 seconds)." % ("applied" if a.what == "apply" else "put back"))
            say("Please send the newest folders in camera_private.")
            raise SystemExit(1)
    say()
    say("All %d steps passed (%s)." % (len(steps), a.what))
    if a.what == "apply":
        say("Now: unplug USB, set File Format XAVC HS 4K or XAVC S 4K at 24p (23.98p), dial to movie, look at the picture, record a few seconds.")
        say("If the camera stops or restarts: do NOT pull the battery yet. Replug USB and run dump_info, then send camera_private.")
        say("To return to stock: battery out for 10 seconds.")


if __name__ == "__main__":
    main()
