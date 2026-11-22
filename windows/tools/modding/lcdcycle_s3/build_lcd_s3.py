"""Design lcdfill_s3_v1: the A7 IV's lcdfill_v2 (rear screen at 3:2 in the open-gate movie state, with the focus frames; F791, F966,
F969) ported to the A7S III 5.01 coprocessor image.

The A7S III image holds the same code and tables at other addresses (modding/A7S3_PORT.md section 26):
  VDF fit-mode function and tables   A7 IV 0x1e4b78 (0x94 bytes)  ->  0x1e4c28, byte for byte
  frame widgets' rectangle tables    A7 IV 0xd7b560, 0xd7b5d8, 0xd7b650 (0x78 bytes each)  ->  0xd4d744, 0xd4d7bc, 0xd4d834, byte for byte
So the seven words of lcdfill_v2 move with them, and every guard of lcdfill_v2 moves with its site. This builder checks each site and
guard against BOTH images: the A7S III bytes must equal the A7 IV bytes at the corresponding A7 IV address.

  C:\\Python313\\python.exe -I -B build/build_lcd_s3.py     writes modding/designs/lcdfill_s3_v1.json and lcdratio32_s3_v1.json

lcdfill_s3_v1 RAN ON AN A7S III (2026-11-22) AND DOES NOT GIVE A 3:2 SCREEN THERE: the rear panel of this camera is not a 3:2 panel, so
the fit word it changes (16:9 picture on a 3:2 panel) is never read (modding/A7S3_PORT.md section 27). It is kept here as built.

Design lcdratio32_s3_v1 replaces it. The panel's aspect code comes from a panel-type byte (0x1e58b8: 0x5f4e04 reads RAM 0x14b9600 for
the rear panel, 0x5f4e16 reads 0x14b9730 for the viewfinder; type 2 = 4:3, type 3 = 3:2, type 1 = 16:9). On a 4:3 panel a 16:9 picture
is letterboxed (fit word 3 at 0x1e4c78, left alone) at the height the picture-ratio function 0x1e4f64 gives: width x 9/16. The live
view of the open-gate state is a 16:9 frame holding the whole 3:2 sensor area, so the right height is width x 2/3:
  0x1e4f98  moveq.w lr, #9  -> #2          0x1e4f9c  it eq; moveq r0, #16 -> #3
(the function's own 3:2 case uses 2 and 3, and adds 3 to the width first: 640 -> 428, as in the camera's tables). The frame widgets
compare the live-view rectangle with a table entry (0x128438: row 0 for a rear panel of type 0, row 2 for the viewfinder, row 1 for
the A7 IV's kind of panel); the 16:9 entries of rows 0 and 2 go from (0, 60, 640, 360) to (0, 26, 640, 428) in all three tables.
The viewfinder is a 4:3 panel too and takes the same constants, so it shows the same picture.

Read-only apart from those files. Nothing here talks to a camera.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402

B = 0x108000
A4 = locate_file.locate("a7iv_602", "cpapp-b.bin").read_bytes()
S3 = locate_file.locate("a7s3_501", "cpapp-b.bin").read_bytes()
FIT_A4, FIT_S3, FIT_LEN = 0x1E4B78, 0x1E4C28, 0x94                 # function (0x50 bytes) + its three tables (0x44 bytes)
TABLES = (("cpActAfWindow (focus area frames)", 0xD7B560, 0xD4D744),
          ("cpActAfWindowRemoteSend (the same frames for a remote viewer)", 0xD7B5D8, 0xD4D7BC),
          ("cpActTrackingFrame (tracking and face frames)", 0xD7B650, 0xD4D834))
TABLE_LEN, ENTRY = 0x78, 0x40                                      # 15 entries of {x, y, w, h} u16; entry 8 = a 16:9 picture on the rear panel
STOCK_RECT, FULL_RECT = (0, 38, 640, 404), (0, 0, 640, 480)
rect = lambda r: struct.pack("<4H", *r)
a4 = lambda a, n: A4[a - B:a - B + n]
s3 = lambda a, n: S3[a - B:a - B + n]


def design():
    assert s3(FIT_S3, FIT_LEN) == a4(FIT_A4, FIT_LEN), "the fit-mode function and its tables are not byte-identical"
    assert S3.count(a4(FIT_A4, 0x50)) == 1, "the fit-mode function is not unique in the A7S III image"
    shift = FIT_S3 - FIT_A4
    sites = [{"ram_address": hex(0x1E4BCC + shift), "old": "03000000", "new": "00000000", "a7iv_address": "0x1e4bcc",
              "note": "VDF fit mode for a 16:9 picture on a 3:2 panel (table for picture code 2, entry for panel code 1): 3 letterbox to 0 fill. "
                      "The rear screen then shows the squeezed 16:9 live view over the whole 3:2 panel, i.e. stretched x32/27 vertically"}]
    assert s3(0x1E4BCC + shift, 4) == bytes.fromhex("03000000")
    guards = [{"ram_address": hex(FIT_S3), "bytes": s3(FIT_S3, 16).hex(), "note": "first 16 bytes of the fit-mode function (A7 IV FUN_001e4b78), as in the file"},
              {"ram_address": hex(FIT_S3 + 0x40), "bytes": s3(FIT_S3 + 0x40, 16).hex(), "note": "last 16 bytes of the fit-mode function before its tables, as in the file"},
              {"ram_address": hex(FIT_S3 + 0x50), "bytes": s3(FIT_S3 + 0x50, 4).hex(), "note": "picture code 2 (16:9), panel code 0 (4:3): 3 letterbox (the viewfinder's entry, left alone)"},
              {"ram_address": hex(FIT_S3 + 0x58), "bytes": s3(FIT_S3 + 0x58, 16).hex(), "note": "picture code 2, panel codes 2 to 5: 0, 0, 0, 2"},
              {"ram_address": hex(FIT_S3 + 0x68), "bytes": s3(FIT_S3 + 0x68, 16).hex(), "note": "the table for picture code 1 (3:2), panel codes 0 to 3: 3, 0, 2, 0"}]
    assert struct.unpack("<I", s3(FIT_S3 + 0x50, 4))[0] == 3 and struct.unpack("<4I", s3(FIT_S3 + 0x58, 16)) == (0, 0, 0, 2)
    assert struct.unpack("<4I", s3(FIT_S3 + 0x68, 16)) == (3, 0, 2, 0)
    for what, t4, t3 in TABLES:
        assert s3(t3, TABLE_LEN) == a4(t4, TABLE_LEN), "frame table %#x is not byte-identical to the A7 IV's %#x" % (t3, t4)
        e = t3 + ENTRY
        assert s3(e, 8) == rect(STOCK_RECT) and s3(e - 8, 8) == rect((107, 0, 426, 480)) and s3(e + 8, 8) == rect((0, 50, 640, 380))
        for off, part in ((0, "x, y"), (4, "w, h")):
            sites.append({"ram_address": hex(e + off), "old": rect(STOCK_RECT)[off:off + 4].hex(), "new": rect(FULL_RECT)[off:off + 4].hex(), "a7iv_address": hex(t4 + ENTRY + off),
                          "note": "%s: expected live-view rectangle for a 16:9 picture on the rear panel, %s: stock letterbox %s to the whole panel %s"
                                  % (what, part, STOCK_RECT, FULL_RECT)})
        guards += [{"ram_address": hex(e - 8), "bytes": s3(e - 8, 8).hex(), "note": "the entry before (1:1 on the rear panel: 107, 0, 426, 480), as in the file"},
                   {"ram_address": hex(e + 8), "bytes": s3(e + 8, 8).hex(), "note": "the entry after (fifth aspect on the rear panel: 0, 50, 640, 380), as in the file"}]
    for s in sites:                                                 # every site: the A7S III word equals the A7 IV word it stands for
        a, a_iv = int(s["ram_address"], 16), int(s["a7iv_address"], 16)
        assert a % 4 == 0 and s3(a, 4) == bytes.fromhex(s["old"]) == a4(a_iv, 4) and s["old"] != s["new"]
    ref = json.loads((ROOT / "modding/designs/lcdfill_v2.json").read_text(encoding="utf8"))
    assert [(s["old"], s["new"]) for s in ref["sites"]] == [(s["old"], s["new"]) for s in sites], "not the words of lcdfill_v2"
    assert [g["bytes"] for g in ref["guards"]] == [g["bytes"] for g in guards], "not the guards of lcdfill_v2"
    return {"design": "lcdfill_s3_v1",
            "title": "A7S III 5.01: rear screen (LCD) at 3:2 in the open-gate movie state with the focus frames: VDF fills the 3:2 panel with the 16:9 live view, "
                     "and the frame widgets expect the live view there",
            "kind": "ram_words", "artifact": "cpapp-b.bin 5.01 (ILCE-7SM3), its loaded image in coprocessor RAM: the words are in the file, the change is made in RAM only",
            "artifact_sha256": hashlib.sha256(S3).hexdigest(), "generated_by": "build/build_lcd_s3.py",
            "ported_from": "lcdfill_v2 (A7 IV 6.02; works on that camera, F969)",
            "table": "VDF fit-mode table %#x and the frame widgets' rectangle tables %s (entry: rear panel, 16:9)" % (FIT_S3 + 0x50, ", ".join(hex(t) for _, _, t in TABLES)),
            "summary": {"sites": len(sites), "bytes": 4 * len(sites), "panel": "rear LCD, 3:2 (panel code 1; inferred for this camera, as it was for the A7 IV)",
                        "picture": "16:9 live view (picture code 2), which in the open-gate state holds the whole 3:2 sensor area squeezed",
                        "fit_stock": "letterbox (3)", "fit_new": "fill (0)", "frame_rectangle_stock": list(STOCK_RECT), "frame_rectangle_new": list(FULL_RECT),
                        "goes_with": ["the A7S III open-gate state (ogsq_s3_v5, outsz2560_s3_v1, ogfile2560_hs_s_s3_v1)", "lcdcycle_s3_v1"]},
            "checked_against": ["cpapp-b.bin 5.01: every site and guard byte", "cpapp-b.bin 6.02 (A7 IV): the same bytes at the address each one is ported from",
                                "lcdfill_v2.json: the same old and new words and the same guard bytes, in the same order"],
            "not_checked": ["on a camera: nothing of this design has run on an A7S III", "that the rear panel reports panel code 1 on this camera"],
            "sites": sites, "guards": guards}


RATIO_FN, RATIO_END = 0x1E4F64, 0x1E5066                         # the picture-ratio function (A7 IV 0x1e4da0, not identical)
CONST = (0x1E4F98, 0x1E4F9C)                                      # moveq.w lr, #n ; it eq + moveq r0, #d  (a 16:9 picture: 9/16)
ROWS = ((0, "a rear panel of type 0 (4:3, this camera's)"), (2, "the viewfinder (4:3)"))
RECT_169, RECT_32 = (0, 60, 640, 360), (0, 26, 640, 428)          # on a 4:3 panel's 640x480 grid: 16:9 and 3:2, centred


def ratio_words(n, d):
    """The two instruction words that give a 16:9 picture the height width x n/d."""
    assert 0 < n < 256 and 0 < d < 256
    return bytes([0x4F, 0xF0, n, 0x0E]), bytes([0x08, 0xBF, d, 0x20])


def design_ratio32():
    assert (s3(CONST[0], 4), s3(CONST[1], 4)) == ratio_words(9, 16), "the 16:9 constants are not where they were read"
    assert s3(FIT_S3 + 0x50, 4) == bytes.fromhex("03000000"), "a 16:9 picture on a 4:3 panel is not letterboxed in the stock table"
    assert s3(0x1E4F80, 6) == bytes.fromhex("4ff0020e0320"), "the function's own 3:2 case is not lr 2, r0 3"
    new = ratio_words(2, 3)
    sites = [{"ram_address": hex(CONST[0]), "old": s3(CONST[0], 4).hex(), "new": new[0].hex(),
              "note": "picture-ratio function, 16:9 picture: `moveq.w lr, #9` to `#2` (the numerator of height = width x n / d)"},
             {"ram_address": hex(CONST[1]), "old": s3(CONST[1], 4).hex(), "new": new[1].hex(),
              "note": "picture-ratio function, 16:9 picture: `it eq; moveq r0, #16` to `#3` (the denominator). With 2 and 3 the function adds 3 to the "
                      "width first, as for its own 3:2 pictures: 640 wide gives 428 high"}]
    guards = [{"ram_address": hex(RATIO_FN), "bytes": s3(RATIO_FN, 16).hex(), "note": "first 16 bytes of the picture-ratio function, as in the file"},
              {"ram_address": hex(0x1E4F88), "bytes": s3(0x1E4F88, 16).hex(), "note": "the 16 bytes before the constants: the flag test and the 100/235 case, as in the file"},
              {"ram_address": hex(0x1E4FA0), "bytes": s3(0x1E4FA0, 16).hex(), "note": "the 16 bytes after the constants, as in the file"},
              {"ram_address": hex(FIT_S3), "bytes": s3(FIT_S3, 16).hex(), "note": "first 16 bytes of the fit-mode function, as in the file"},
              {"ram_address": hex(FIT_S3 + 0x50), "bytes": s3(FIT_S3 + 0x50, 4).hex(), "note": "fit mode for a 16:9 picture on a 4:3 panel: 3 letterbox (what makes the constants count)"}]
    for what, _, t3 in TABLES:
        for row, panel in ROWS:
            e = t3 + 8 * (5 * row + 3)                              # column 3 = a 16:9 picture
            assert s3(e, 8) == rect(RECT_169), "%#x is not the 16:9 entry (0, 60, 640, 360)" % e
            for off, part in ((0, "x, y"), (4, "w, h")):
                sites.append({"ram_address": hex(e + off), "old": rect(RECT_169)[off:off + 4].hex(), "new": rect(RECT_32)[off:off + 4].hex(),
                              "note": "%s, %s: expected live-view rectangle for a 16:9 picture, %s: %s to %s" % (what, panel, part, RECT_169, RECT_32)})
            guards += [{"ram_address": hex(e - 8), "bytes": s3(e - 8, 8).hex(), "note": "the entry before (1:1 picture), as in the file"},
                       {"ram_address": hex(e + 8), "bytes": s3(e + 8, 8).hex(), "note": "the entry after (17:9 picture: 0, 71, 640, 338), as in the file"}]
    assert all(int(x["ram_address"], 16) % 4 == 0 and s3(int(x["ram_address"], 16), 4) == bytes.fromhex(x["old"]) and x["old"] != x["new"] for x in sites)
    # the letterbox the function gives for these constants on an 800x600 panel, in the widgets' 640x480 grid: within their tolerance of 5
    h = ((((800 + 3) << 8) // 3) * 2 >> 8) & 0xFFFE
    got = (0, (600 - h) // 2 * 640 / 800, 640, h * 640 / 800)
    assert all(abs(a - b) <= 2 for a, b in zip(got, RECT_32)), got
    return {"design": "lcdratio32_s3_v1",
            "title": "A7S III 5.01: rear screen and viewfinder show the open-gate live view at 3:2: the letterbox of a 16:9 picture is given the height "
                     "width x 2/3, and the frame widgets expect the live view there",
            "kind": "ram_words", "artifact": "cpapp-b.bin 5.01 (ILCE-7SM3), its loaded image in coprocessor RAM: the words are in the file, the change is made in RAM only",
            "artifact_sha256": hashlib.sha256(S3).hexdigest(), "generated_by": "build/build_lcd_s3.py",
            "replaces": "lcdfill_s3_v1, which changes a word this camera does not read (camera test 2026-11-22: the screen stayed at 16:9)",
            "summary": {"sites": len(sites), "bytes": 4 * len(sites), "panel": "rear LCD and viewfinder, both 4:3 panels (panel code 0); inferred from the camera test and the firmware",
                        "picture": "16:9 live view (picture code 2), which in the open-gate state holds the whole 3:2 sensor area squeezed",
                        "ratio_stock": "9/16", "ratio_new": "2/3", "frame_rectangle_stock": list(RECT_169), "frame_rectangle_new": list(RECT_32),
                        "goes_with": ["the A7S III open-gate state (ogsq_s3_v5, outsz2560_s3_v1, ogfile2560_hs_s_s3_v1)", "lcdcycle_s3_v2"]},
            "while_applied": "every 16:9 picture on the rear screen and in the viewfinder is shown at 3:2 (other movie formats look squeezed there); HDMI is unchanged",
            "checked_against": ["cpapp-b.bin 5.01: every site and guard byte", "the function's own 3:2 case (lr 2, r0 3) and the tables' 3:2 height 428"],
            "not_checked": ["on a camera: this design has not run", "the panel-type bytes 0x14b9600 and 0x14b9730 (not read yet; the dump of helper s3read_v8 reads them)",
                            "which table row the rear panel's widgets use (rows 0 and 2 are both set)"],
            "sites": sites, "guards": guards}


if __name__ == "__main__":
    for d in (design(), design_ratio32()):
        out = ROOT / ("modding/designs/%s.json" % d["design"])
        out.write_text(json.dumps(d, indent=1) + "\n", encoding="utf8", newline="\n")
        print("%s: %d sites %s; %d guards" % (out.name, len(d["sites"]), ", ".join(s["ram_address"] for s in d["sites"]), len(d["guards"])))
