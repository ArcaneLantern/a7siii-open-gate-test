"""A7S III (ILCE-7SM3) firmware 5.01: run one of the two READ-ONLY helper libraries and save what it reports.

  python s3_run.py check --dry-run | --selftest
  python s3_run.py dump  --dry-run | --selftest
  python s3_run.py check --go --firmware-shown 5.01
  python s3_run.py dump  --go --firmware-shown 5.01 [--clear-result SHA256]

  check   identity of the camera's software and what every site of the open-gate designs holds now: READY / NOT READY
  dump    the same, plus kernel and memory facts, the coprocessor's logs and some of its tables, for the people doing the
          port. Run it once with the dial on stills after a cold boot, and once more after looking at a 4K 24p movie picture.

Both libraries only read. Each creates one file, its result, on the camera's RAM disk; this script fetches it. The
library is written to the camera's service partition, loaded once, and deleted again in the same session.

It is the A7 IV runner (ct6_level1_run.py: fixed packet list, guard, simulated camera, the same session steps) with
this camera's libraries, pins and result reader. Nothing here can send a memory write: neither library contains one.
"""
import argparse
import json
import platform
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CT1_usb_first_contact"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "helper"))
sys.path.insert(0, str(HERE / "helper_s3"))
import ct1_common as c  # noqa: E402
import ct6_level1_run as R  # noqa: E402

FIRMWARE, MODEL, BUILD = "5.01", "ILCE-7SM3", "a7s3_501"
S3 = HERE / "helper_s3"
PINS = {"check": ("libJit_s3_check.so", "e8adeae97caab3b26958068de0dcf1dacd76ad8483333b5cf23f91743d6a91dc"),
        "dump": ("libJit_s3_dump.so", "ad416c29151f435f45aa71c6bb8f4bb9cf24c85bf098945642e92bf76f37f91c")}
LEVELS = {"check": 101, "dump": 102}              # numbers outside the A7 IV runner's own levels: none of its level-specific code runs
# THE WRITE STEPS. Each is one library built from the A7 IV helper's write code with this camera's tables (helper_s3/build_s3_write.sh).
# They change the running camera's memory until a cold boot. They are run through s3_apply.py, never by a launcher of the read-only kit,
# and the libraries are not in the published kit unless it was published with --include-write.
WRITE_STEPS = {
    "L5": ("libJit_s3_L5.so", "5bc1bdcee924e1bd30e405fc29c269440b2c36548ede357d8e34c5d21cc4efa3", "apply the sensor-side design ogsq_s3_v5 (sensor cells, two records, the stored record)"),
    "L6": ("libJit_s3_L6.so", "5ea7f7cac2a2bda8628a3dda9012532c7c508f6ea5ce9603021474ee5249f69c", "put back the sensor-side design ogsq_s3_v5"),
    "L16": ("libJit_s3_L16.so", "ff206663b7df61ef6e20d182bbefba3e5341f2ddf1df588ffb38123f70eadc67", "apply the output size outsz2560_s3_v1 (one word)"),
    "L17": ("libJit_s3_L17.so", "b56744396d5035c3862b276c4e9a85e950c0bbe890accd849bb8102fee0533ba", "put back the output size outsz2560_s3_v1"),
    "L19": ("libJit_s3_L19.so", "85b5882d0fd2f2525a6eab109ed7ee8ea2f53be42351b56af52e2e7f7f47d588", "apply the encoder-side design ogfile2560_hs_s_s3_v1 (101 + 4 sites)"),
    "L20": ("libJit_s3_L20.so", "3683c64f54784cfb7fde5af0c4b4096cb6cd3d58cc9c3d988c92abd1c9358f86", "put back the encoder-side design ogfile2560_hs_s_s3_v1"),
    # The rear-screen steps (optional, on top of the open-gate state). S = the same level 16/17 code with the screen words; C = the same
    # level 19/20 code with the C3 routine for appFw.so. The digits are the level the library reports in its result's first line.
    "S16": ("libJit_s3_S16.so", "ffd20cf41d5bf2bc2376ef97f1d78dd1c9e4e307c4f1f4949d8af60e2de46333", "apply the screen words lcdratio32_s3_v1 (3:2 picture on the rear screen and viewfinder, and the focus-frame rectangles: 14 words)"),
    "S17": ("libJit_s3_S17.so", "1f3afee9fd04b0fa90a6455a8b8c65f108c348c6c4336339da9409a586d317fc", "put back the screen words lcdratio32_s3_v1"),
    "C19": ("libJit_s3_C19.so", "3a90cc6e280826c7f3aa70eb4aedef40aca63eb7c5b59957d9b6a6cfd88bde0f", "apply the C3 preview routine lcdcycle_s3_v3 (3:2, 2:1, 2.25:1, 2.4:1; code in appFw.so: the routine, then one branch to it)"),
    "C20": ("libJit_s3_C20.so", "9de9a4924d4bfc8a2c253168e13c121732dc9868f9a2f350c9eb97b4816ae069", "put back the C3 preview routine lcdcycle_s3_v3"),
}
PINS.update({k: v[:2] for k, v in WRITE_STEPS.items()})
LEVELS.update({k: {"L": 200, "S": 300, "C": 400}[k[0]] + int(k[1:]) for k in WRITE_STEPS})
WHICH = "check"


def write_result(data):
    """The facts of a write step's result (the A7 IV helper's report format)."""
    import hashlib
    text = data.decode("utf8", "replace")
    lines = text.split("\n")
    pick = lambda start: next((ln for ln in lines if ln.startswith(start)), None)
    outcome = ("UNDO INCOMPLETE" if pick("!! UNDO INCOMPLETE") else "DONE" if pick("DONE: ") else "NOTHING TO DO" if pick("NOTHING TO DO") else
               "NOT DONE (everything put back)" if pick("NOT DONE: ") else "NOTHING WRITTEN" if any("nothing is written" in ln for ln in lines) else "UNKNOWN")
    problems = [ln for ln in lines if ln.startswith("!!")]
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "header_ok": lines[0].startswith("readcheck 1 level %s" % WHICH[1:]),
            "euid": "see the result", "sections": [ln for ln in lines if ln.startswith("== ")], "problems": len(problems),
            "complete": any(ln.startswith("== done") for ln in lines[-3:]),
            "s3": {"step": WHICH, "what": WRITE_STEPS[WHICH][2], "outcome": outcome, "ok": outcome in ("DONE", "NOTHING TO DO"),
                   "outcome_line": pick("DONE: ") or pick("NOTHING TO DO") or pick("NOT DONE: ") or pick("!! UNDO INCOMPLETE"), "problem_lines": problems}}


def reference():
    return json.loads((S3 / "s3_reference.json").read_text(encoding="utf8"))


def expected():
    return json.loads((S3 / "s3_expected.json").read_text(encoding="utf8"))


# ------------------------------------------------------------ reading a result

def check_result(data):
    """The facts of a result file. Keys the A7 IV runner prints, plus this helper's own under "s3"."""
    if WHICH in WRITE_STEPS:
        return write_result(data)
    text = data.decode("utf8", "replace")
    lines = text.split("\n")
    head = lines[0] if lines else ""
    count = lambda pat: sum(1 for ln in lines if re.search(pat, ln))
    verdict = next((ln for ln in lines if ln.startswith("VERDICT ")), "no verdict line")
    pages = {}
    for ln in lines:
        if ln.startswith("cppage "):
            _, name, addr, hx = ln.split(" ", 3)
            pages[int(addr, 16)] = (name, bytes.fromhex(hx.strip()))
    sites = []
    for ln in lines:
        m = re.match(r"site (\S+) (0x[0-9a-f]+) len (\d+)(?: bytes (?:differing from stock )?(\S+))?  (STOCK|TARGET|OTHER.*|NOT READ)$", ln)
        if m:
            sites.append({"name": m.group(1), "address": m.group(2), "length": int(m.group(3)), "shown": m.group(4), "state": m.group(5)})
    s3 = {"header": head, "verdict": verdict, "ready": verdict.startswith("VERDICT READY"),
          "identity_same": count(r"SAME as the 5\.01 update$"), "identity_differs": count(r"DIFFERS from the 5\.01 update$"),
          "coprocessor_sites": sites, "libmpr_sites": [ln for ln in lines if ln.startswith("lm ")],
          "avcam_stock": count(r"^av .*  STOCK$"), "avcam_target": count(r"^av .*  TARGET$"), "avcam_other": count(r"^av .*  OTHER$"),
          "avcam_guards": [ln for ln in lines if ln.startswith("guard ")], "problem_lines": [ln for ln in lines if ln.startswith("!!")],
          "pages": len(pages)}
    cmd = re.search(r"== file /proc/cmdline\n(.*?)\n== end", text, re.S)
    ver = re.search(r"== file /proc/version\n(.*?)\n== end", text, re.S)
    s3["kernel_command_line"], s3["kernel_version"] = (cmd.group(1).strip() if cmd else None), (ver.group(1).strip() if ver else None)
    if pages:
        s3["decoded"] = decode_pages(pages)
    import hashlib
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "header_ok": head.startswith("s3read ") and "ILCE-7SM3 5.01" in head, "euid": "not read",
            "sections": [ln for ln in lines if ln.startswith("== ")], "problems": len(s3["problem_lines"]), "complete": "== done" in lines[-3:],
            "s3": s3, "_pages": pages}


def decode_pages(pages):
    """What the dump's coprocessor pages say, set against the firmware file's tables."""
    ref, out = reference(), {}

    def mem(addr, n):
        b = bytearray()
        while n:
            page = pages.get(addr & ~0xFFF)
            if page is None:
                return None
            take = min(n, 4096 - (addr & 0xFFF))
            b += page[1][addr & 0xFFF:(addr & 0xFFF) + take]
            addr, n = addr + take, n - take
        return bytes(b)

    # the sensor register shadow against each column of the register matrix
    rows = [(a, bytes.fromhex(h)) for a, h in ref["matrix"]]
    shadow = [(a, mem(a, 1)) for a, _ in rows]
    if all(v is not None for _, v in shadow):
        score = [sum(1 for (a, cols), (_, v) in zip(rows, shadow) if cols[k] == v[0]) for k in range(12)]
        best = max(range(12), key=lambda k: score[k])
        users = [ref["mode_ids"][i] for i, (col, _) in enumerate(ref["column_map"]) if col == best]
        out["sensor_registers"] = {"rows": len(rows), "rows_equal_per_column": score, "closest_column": best, "modes_using_it": users,
                                   "rows_differing_from_it": [[i, hex(a), cols[best], v[0]] for i, ((a, cols), (_, v)) in enumerate(zip(rows, shadow)) if cols[best] != v[0]][:64],
                                   "window_rows_6_7_24_42": [shadow[i][1][0] for i in (6, 7, 24, 42)]}
    # the matrix itself as the camera holds it
    m0 = int(ref["matrix_address"], 16)
    got = mem(m0, 16 * len(rows)) if (m0 & ~0xFFF) in pages else None
    if got is not None:
        want = b"".join(struct.pack("<I", a) + cols for a, cols in rows)
        out["matrix_equals_file"] = got == want
    # the stored drive-parameter records against the emulated ones
    r0, size = int(ref["records_address"], 16), ref["record_size"]
    recs = {}
    for i, mid in enumerate(ref["mode_ids"]):
        b = mem(r0 + i * size, size)
        if b is None:
            continue
        emu = bytes.fromhex(ref["emulated_stock_records"][mid])
        diff = [o for o in range(size) if b[o] != emu[o]]
        recs[mid] = {"index": i, "all_zero": not any(b), "bytes_differing_from_emulation": len(diff), "offsets": [hex(o) for o in diff[:48]], "record": b.hex()}
    out["stored_records"] = recs
    t = mem(int(ref["size_table_address"], 16), 128)
    if t is not None:
        out["size_table"] = [list(struct.unpack_from("<HHI", t, 8 * k)) for k in range(16)]
    # v3: the second scaler's state. The A7 IV's layouts at the addresses matched for this build; the three "predicted" addresses are the
    # A7 IV's distance from the division block and are NOT confirmed, so every place where a picture size of interest occurs is listed too.
    st = {}
    blk = mem(0x140043C, 0x20)                    # A7 IV 0x145091c: in w, in h, start x, y, w-1, h-1, start fractions, size fractions (u16)
    if blk is not None:
        w = struct.unpack_from("<10H", blk)
        st["second_scaler_block_0x140043c"] = {"words": list(w), "start": [round(w[2] + w[6] / 4096, 3), round(w[3] + w[7] / 4096, 3)],
                                                        "size": [round(w[4] + w[8] / 4096, 3), round(w[5] + w[9] / 4096, 3)]}
    inp = mem(0x1400478, 8)                       # A7 IV 0x1450958
    if inp is not None:
        st["second_scaler_input_0x1400478"] = list(struct.unpack_from("<4H", inp))
    ws = mem(0x11B5C40, 0xDC)                     # A7 IV 0x11e1510: pixel aspect +0x48, scales +0x4c / +0x50 (Q12), zoom +0x24 (Q16)
    if ws is not None:
        st["resize_work_0x11b5c40"] = {"pixel_aspect_q12": struct.unpack_from("<i", ws, 0x48)[0], "scale_h_q12": struct.unpack_from("<i", ws, 0x4C)[0],
                                       "scale_v_q12": struct.unpack_from("<i", ws, 0x50)[0], "zoom_q16": struct.unpack_from("<i", ws, 0x24)[0], "head": ws[:0x60].hex()}
    se = mem(0x1401FF8, 0x20)                     # A7 IV 0x1452488: +0x10 flags, +0x18 / +0x1a units
    if se is not None:
        st["resize_settings_0x1401ff8"] = se.hex()
    dv = mem(0x1400888, 0x5A0)                    # A7 IV 0x1450d70: per unit, stride 0x150: +0xc in start, +0x10 in width, +0x20 out width
    if dv is not None:
        st["division_units_0x1400888"] = [{"in_start": struct.unpack_from("<I", dv, k * 0x150 + 0xC)[0], "in_width": struct.unpack_from("<I", dv, k * 0x150 + 0x10)[0],
                                           "out_width": struct.unpack_from("<I", dv, k * 0x150 + 0x20)[0]} for k in range(4)]
    seen = {}
    pairs = {(4240, 2832), (4240, 2392), (4240, 2385), (4240, 2848), (4240, 2408), (3840, 2560), (3840, 2160), (1920, 1080), (2144, 2392), (2096, 2392), (2176, 2408)}
    for addr, (name, blob) in sorted(pages.items()):
        if name not in ("context", "resizework", "resizestate"):
            continue
        for o in range(0, 4096 - 3, 2):
            p = struct.unpack_from("<HH", blob, o)
            if p in pairs:
                seen.setdefault("%dx%d" % p, []).append(hex(addr + o))
    st["where_sizes_occur"] = {k: v[:40] for k, v in sorted(seen.items())}
    if any(n in ("context", "resizework", "resizestate") for n, _ in pages.values()):
        out["scaler_state"] = st
    # v8: what the screen steps change, and what decides them. The panel's aspect code comes from a panel-type byte (0x1e58b8): type 2 is
    # a 4:3 panel, 3 a 3:2 panel, 1 a 16:9 one. A 16:9 picture on a 4:3 panel is letterboxed at width x n/d, n and d being the two constants.
    disp = {}
    types = mem(0x14B9600, 1), mem(0x14B9730, 1)
    if None not in types:
        name = {1: "16:9", 2: "4:3", 3: "3:2"}
        rear, finder = (1 if types[0][0] >= 4 else types[0][0]), min(types[1][0], 2)
        disp["panel_types"] = {"rear_0x14b9600": types[0][0], "rear_aspect": name.get(rear, "none"), "viewfinder_0x14b9730": types[1][0], "viewfinder_aspect": name.get(finder, "none")}
    fit, con = mem(0x1E4C78, 8), mem(0x1E4F98, 8)
    if fit is not None and con is not None:
        n, d = con[2], con[6]
        known = {(9, 16): "16:9, stock", (2, 3): "3:2", (1, 2): "2:1", (5, 12): "2.4:1"}
        disp["fit_16x9_picture"] = {"on_4x3_panel_0x1e4c78": struct.unpack_from("<I", fit, 0)[0], "on_3x2_panel_0x1e4c7c": struct.unpack_from("<I", fit, 4)[0]}
        disp["ratio_constants_0x1e4f98"] = {"words": con.hex(), "height": "width x %d/%d" % (n, d),
                                            "state": known.get((n, d), "unknown") if con[:2] + con[3:6] + con[7:] == bytes.fromhex("4ff00e08bf20") else "not the expected instructions"}
    rows = {}
    for t in (0xD4D744, 0xD4D7BC, 0xD4D834):
        b = mem(t, 0x78)
        if b is not None:
            rows[hex(t)] = {"row%d" % r: list(struct.unpack_from("<4H", b, 8 * (5 * r + 3))) for r in range(3)}
    if rows:
        disp["frame_rectangles_16x9_picture"] = rows
    if disp:
        out["display"] = disp
    # The camera core's periodic log record (0x1401064, filled at 0x4297d8 when its sensor readings update). It is the one place a dump
    # shows state from BEFORE the USB session: at dump time the sensor sleeps (drive mode 1) and the live state is the session's.
    # +4 a time count, +8 the drive mode id, +0xb [context+0x364], +0xc [context+0x368], +0xd a core state number, +0xe [context+0x2a4].
    # In the ten dumps read so far (modding/A7S3_PORT.md section 28): stills live view 0x5020 reads 2 / 7 / 8; a 4K mode sampled in
    # standby 2 / 7 / 1; sampled after a recording had started 1 / 9 / 1 (once 2 / 9 / 1). So the state number tells standby from
    # recording, not a right picture from a wrong one.
    rec = mem(0x1401064, 0x10)
    if rec is not None:
        out["core_log_record"] = {"time": struct.unpack_from("<I", rec, 4)[0], "drive_mode": hex(struct.unpack_from("<H", rec, 8)[0]), "context_0x364": rec[0xB],
                                  "context_0x368": rec[0xC], "state": rec[0xD], "context_0x2a4": rec[0xE]}
    return out


# ------------------------------------------------------------ the A7 IV runner, pointed at this camera

def known_answer(session, camera):
    want = (S3 / "DeviceInfo.xml").read_bytes()
    there, data = R.read(camera, R.KNOWN_PATH)
    if not there or data != want:
        raise c.StopTest("DeviceInfo.xml is not the file of the 5.01 update (%s); nothing else is sent"
                         % ("the camera returned no file" if not there else "%d bytes, SHA-256 %s" % (len(data), c.sha256(data)[:16])))
    session.say("Known-answer read: DeviceInfo.xml equals the 5.01 file (the A7 IV has the same file: the helper itself checks which camera this is)")


def run_helper(data):
    """What loading the uploaded bytes gives on a model A7S III: the real AArch64 code in Unicorn if it is installed, else a canned text."""
    if WHICH in WRITE_STEPS:                        # the write libraries are emulated by helper_s3/emu_s3_write.py; here only the session flow is simulated
        text = "readcheck 1 level %s\neuid 0\n== level %s\nDONE: every site holds the target bytes (canned)\n== done, bytes written before this line: 0\n" % (WHICH[1:], WHICH[1:])
        return text.encode(), "canned"
    try:
        import emu_s3
    except Exception:
        text = "s3read s3read_v8 %s for ILCE-7SM3 5.01; read-only\n== file /proc/version\nLinux (simulated)\n\n== end 18 bytes\n== summary\nVERDICT READY (canned)\n== done\n" % WHICH
        return text.encode(), "canned"
    r, text = emu_s3.run(bytes(data))
    if r.bad:
        raise AssertionError("the emulated helper stopped: %s" % r.bad)
    return text.encode(), "emulated"


def make_sim(lib, files=None, fault=None):
    sim = _make_sim(lib, files, fault)
    if "/usr/share/pmbp/DeviceInfo.xml" not in (files or {}):
        sim.fs["/usr/share/pmbp/DeviceInfo.xml"] = (S3 / "DeviceInfo.xml").read_bytes()
    return sim


def use(which):
    """Point the runner's module state at one of this camera's two libraries."""
    global WHICH
    WHICH = which
    name, sha = PINS[which]
    if not (S3 / name).is_file():
        raise SystemExit("%s is not in this kit%s. Nothing was sent." % (name, " (the write steps are not published yet)" if which in WRITE_STEPS else ""))
    R.LEVEL, R.DESIGN, R.LIB, R.LIB_SHA256 = LEVELS[which], "og4k_data_v1", S3 / name, sha
    R.check_result, R.known_answer, R.run_helper, R.make_sim = check_result, known_answer, run_helper, make_sim
    c.EXPECTED_FIRMWARE = FIRMWARE
    return R.library()


_make_sim = R.make_sim


def selftest(lib):
    done = []

    def check(cond, what):
        if not cond:
            raise AssertionError("self-test failed: " + what)
        done.append(what)

    W, D = "SET_FILE2", "FILE_DELETE2"
    s, sim, stopped = R.simulate(lib, R.body_run)
    r = s.results.get("ct6", {})
    check(not stopped and not sim.unexpected and R.sent(s).count(W) == 1 and R.sent(s).count(D) == 1, "normal run: one write, one delete, nothing off the list")
    check(R.sent(s).index(D) < len(R.sent(s)) - 2 and R.sent(s)[-1] == "GET_FILE2", "normal run: the delete comes before the result is read")
    check(R.LIB_PATH.decode() not in sim.fs and sim.loads == 1, "normal run: the library was loaded once and is gone afterwards")
    f = r.get("result", {}).get("s3", {})
    if WHICH in WRITE_STEPS:
        check(f.get("ok") and r["result"]["header_ok"], "normal run: the step's result is read as DONE")
    else:
        check(f.get("ready") and not f.get("identity_differs"), "normal run: the %s helper reports a stock 5.01 camera as READY" % sim.how)
    if sim.how == "emulated":
        check(len(f["coprocessor_sites"]) == len(expected()["cp_sites"]) and f["avcam_stock"] == 101 and len(f["libmpr_sites"]) == 4, "normal run: every coprocessor site, 4 libmpr and 101 av-cam sites are reported")
        if WHICH == "dump":
            d = f.get("decoded", {})
            check(d.get("matrix_equals_file") and len(d.get("stored_records", {})) == 40 and d.get("size_table"), "dump: the pages decode (matrix, 40 records, size table)")
            dp = d.get("display", {})
            check(dp.get("ratio_constants_0x1e4f98", {}).get("state") == "16:9, stock" and dp.get("fit_16x9_picture") == {"on_4x3_panel_0x1e4c78": 3, "on_3x2_panel_0x1e4c7c": 3}
                  and all(v == {"row0": [0, 60, 640, 360], "row1": [0, 38, 640, 404], "row2": [0, 60, 640, 360]} for v in dp.get("frame_rectangles_16x9_picture", {"x": 0}).values())
                  and "panel_types" in dp, "dump: the display pages decode (stock ratio 9/16, fit words, the three tables' rows, panel types)")
    s, sim, stopped = R.simulate(lib, R.body_run, files={R.LIB_PATH.decode(): b"someone else's"})
    check(stopped and W not in R.sent(s) and D not in R.sent(s), "a foreign libJit.so on the camera: stops, nothing written, nothing deleted")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/tmp_wbshd/readcheck_result.txt": b"old"})
    check(stopped and W not in R.sent(s), "a result already on the RAM disk: stops, nothing written")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/tmp/jbusy": b""})
    check(stopped and W not in R.sent(s), "/tmp/jbusy present: stops, nothing written")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/usr/share/pmbp/DeviceInfo.xml": b"<other camera/>"})
    check(stopped and len(R.sent(s)) == 2, "another DeviceInfo.xml: stops after the known-answer read")
    s, sim, stopped = R.simulate(lib, R.body_run, fault="load")
    check(stopped and R.sent(s).count(D) == 1 and R.LIB_PATH.decode() not in sim.fs, "a camera that cannot load the library: it is still deleted")
    check(len(R.refusals(lib)) == 15, "the guard refuses the 15 listed packets (changed library, other paths, backup, flash and debug writes ...)")
    return done


def report(session, facts, which):
    f = facts["s3"]
    if which in WRITE_STEPS:
        lines = ["A7S III 5.01 step %s: %s" % (which, f["what"]), "OUTCOME: %s" % f["outcome"], str(f["outcome_line"])] + ["  " + ln for ln in f["problem_lines"]]
        session.save_bytes("s3_report.txt", ("\n".join(lines) + "\n").encode())
        for ln in lines:
            session.say(ln)
        return
    lines = ["A7S III 5.01 %s, %s" % (which, time.strftime("%Y-%m-%d %H:%M:%S")), f["header"], f["verdict"],
             "identity: %d same, %d differ" % (f["identity_same"], f["identity_differs"]),
             "kernel: %s" % f["kernel_version"], "command line: %s" % f["kernel_command_line"]]
    for s in f["coprocessor_sites"]:
        lines.append("  coprocessor %-16s %s len %-4d %s%s" % (s["name"], s["address"], s["length"], s["state"], "" if s["shown"] is None else "  (" + s["shown"] + ")"))
    lines += ["  " + ln for ln in f["libmpr_sites"]] + ["  " + ln for ln in f["avcam_guards"]]
    lines.append("  av-cam.bin sites: %d stock, %d target, %d other" % (f["avcam_stock"], f["avcam_target"], f["avcam_other"]))
    lines += ["problem lines:"] + ["  " + ln for ln in f["problem_lines"]] if f["problem_lines"] else ["no problem lines"]
    d = f.get("decoded")
    if d:
        sr = d.get("sensor_registers")
        if sr:
            lines.append("sensor register shadow: closest matrix column %d (%d of %d rows equal; modes %s); window rows 6/7/24/42 hold %s"
                         % (sr["closest_column"], sr["rows_equal_per_column"][sr["closest_column"]], sr["rows"], ", ".join(sr["modes_using_it"]), sr["window_rows_6_7_24_42"]))
        lines.append("register matrix equals the file: %s" % d.get("matrix_equals_file"))
        zero = [m for m, v in d.get("stored_records", {}).items() if v["all_zero"]]
        same = [m for m, v in d.get("stored_records", {}).items() if not v["bytes_differing_from_emulation"]]
        lines.append("stored drive-parameter records: %d read, %d equal to the emulated ones, %d all zero" % (len(d.get("stored_records", {})), len(same), len(zero)))
        v = d.get("stored_records", {}).get("0x8c0")
        if v:
            lines.append("  mode 0x8c0: %d bytes differ from the emulation at %s" % (v["bytes_differing_from_emulation"], ", ".join(v["offsets"])))
        if d.get("size_table"):
            lines.append("movie size table: " + "; ".join("%dx%d id %#x" % tuple(r) for r in d["size_table"]))
        ss = d.get("scaler_state")
        if ss:
            lines.append("second scaler state (addresses matched to the A7 IV's; the two 'predicted' ones are not confirmed):")
            b = ss.get("second_scaler_block_0x140043c")
            if b:
                lines.append("  block: words %s -> takes %s x %s from %s" % (b["words"], b["size"][0], b["size"][1], b["start"]))
            if "second_scaler_input_0x1400478" in ss:
                lines.append("  input words: %s" % ss["second_scaler_input_0x1400478"])
            rw = ss.get("resize_work_0x11b5c40")
            if rw:
                lines.append("  resize work: pixel aspect %d/4096, scales %d and %d /4096, zoom %d/65536" % (rw["pixel_aspect_q12"], rw["scale_h_q12"], rw["scale_v_q12"], rw["zoom_q16"]))
            if "division_units_0x1400888" in ss:
                lines.append("  division units: %s" % ss["division_units_0x1400888"])
            for k, v in ss.get("where_sizes_occur", {}).items():
                lines.append("  %s at %s%s" % (k, ", ".join(v[:10]), " ..." if len(v) > 10 else ""))
        cl = d.get("core_log_record")
        if cl:
            lines.append("camera core's last log record before this session: time %d, drive mode %s, values %d / %d / %d (state 7 = standby, 9 = recording, as seen so far)"
                         % (cl["time"], cl["drive_mode"], cl["context_0x364"], cl["state"], cl["context_0x2a4"]))
        dp = d.get("display")
        if dp:
            lines.append("display (what the screen steps change):")
            if "panel_types" in dp:
                t = dp["panel_types"]
                lines.append("  panel types: rear %d (%s), viewfinder %d (%s)" % (t["rear_0x14b9600"], t["rear_aspect"], t["viewfinder_0x14b9730"], t["viewfinder_aspect"]))
            if "ratio_constants_0x1e4f98" in dp:
                r, ft = dp["ratio_constants_0x1e4f98"], dp["fit_16x9_picture"]
                lines.append("  a 16:9 picture: height = %s (%s); fit word on a 4:3 panel %d, on a 3:2 panel %d" % (r["height"], r["state"], ft["on_4x3_panel_0x1e4c78"], ft["on_3x2_panel_0x1e4c7c"]))
            for t, rw in dp.get("frame_rectangles_16x9_picture", {}).items():
                lines.append("  frame table %s: row 0 %s, row 1 %s, row 2 %s" % (t, rw["row0"], rw["row1"], rw["row2"]))
    session.save_bytes("s3_report.txt", ("\n".join(lines) + "\n").encode())
    for ln in lines[:8] + lines[-6:]:
        session.say(ln)


def last_saved_sha():
    """The SHA-256 of the result the newest saved session of this kit fetched, or None."""
    root = c.PRIVATE_ROOT
    if not root.is_dir():
        return None
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("CT6_")), reverse=True):
        try:
            return json.loads((folder / "manifest.json").read_text(encoding="utf8"))["results"]["ct6"]["result"]["sha256"]
        except (OSError, KeyError, TypeError, ValueError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=sorted(PINS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--remove-only", action="store_true")
    ap.add_argument("--clear-result", metavar="SHA256", help="first delete the result file of an earlier run from the RAM disk, only if its SHA-256 is this")
    ap.add_argument("--firmware-shown")
    ap.add_argument("--writes-memory", action="store_true", help="needed for a write step (L5, L6, L16, L17, L19, L20, S16, S17, C19, C20): it changes the running camera's memory")
    a = ap.parse_args()
    if a.which in WRITE_STEPS and a.go and not (a.dry_run or a.selftest) and not a.writes_memory:
        raise SystemExit("%s is a write step: %s. It needs --writes-memory as well. Use s3_apply.py. Nothing was sent." % (a.which, WRITE_STEPS[a.which][2]))
    lib = use(a.which)
    if a.dry_run or a.selftest:
        if a.selftest:                              # --dry-run and --selftest win over --go (the launchers always pass --go): nothing is sent
            for line in selftest(lib):
                print("PASS  " + line)
            print("all checks passed; nothing was sent to any device")
        else:
            print("\n".join(R.dry_run_lines(lib)))
        return
    if not a.go or a.firmware_shown != FIRMWARE:
        raise SystemExit("A live run needs --go and --firmware-shown %s (the version the camera's menu shows). Nothing was sent." % FIRMWARE)
    R.refusals(lib)
    selftest(lib)                                   # the flow must pass on the simulated camera on the day, before the real one
    import ct1_stage2_service as service
    # A result left on the RAM disk by the run before stops a new run (seen on the first A7S III session). Without --clear-result the newest
    # result saved on this PC is named: the runner deletes the camera's file only if its SHA-256 is that one, i.e. only a result already here.
    R.CLEAR_SHA = a.clear_result or last_saved_sha()
    body = R.body_remove_only if a.remove_only else R.body_run
    with c.Session("remove_only" if a.remove_only else "s3_%s" % a.which, test="CT6") as session:
        session.results.update(firmware_shown_on_camera=a.firmware_shown, model=MODEL, which=a.which, library_sha256=PINS[a.which][1],
                               pc={"platform": platform.platform(), "python": sys.version.split()[0]})
        inner = service.connect(session)
        try:
            R.service_session(session, inner, lambda cam: body(session, cam, lib), lib)
            facts = session.results.get("ct6", {}).get("result")
            if facts and not a.remove_only:
                pages = facts.pop("_pages", {})
                for addr, (name, blob) in sorted(pages.items()):
                    session.save_bytes("cp_%s_%08x.bin" % (name, addr), blob)
                report(session, facts, a.which)
        finally:
            time.sleep(3)
            c.print_pnp(session, "after the stop request")
            out = session.results.get("ct6", {})
            print("Library sent: %s. On the camera now: %s." % (
                "yes" if out.get("library_sent") else "no",
                {False: "no (confirmed)", True: "YES", None: "not sent" if not out.get("library_sent") and not a.remove_only else "UNKNOWN"}[out.get("library_on_camera_after")]))
            if a.which in WRITE_STEPS:
                print("This was a WRITE step. A cold boot (battery out for 10 seconds) undoes everything written. On the tester's A7S III the power switch did too: keep the camera on between steps.")
            else:
                print("Nothing on the camera was changed. Unplug and replug the USB cable before another run; a cold boot (battery out) clears the result file.")


if __name__ == "__main__":
    main()
