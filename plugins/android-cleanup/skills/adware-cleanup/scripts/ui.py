"""Drive the phone screen.
  python ui.py --serial X find [pattern]   on-screen elements with tap coordinates: "(x,y) 'text' 'content-desc'"
  python ui.py --serial X shot out.png     save a screenshot (safe on Windows, where `>` corrupts PNGs)
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script folder
from adbtools import Phone, add_serial_arg


def main():
    ap = argparse.ArgumentParser()
    add_serial_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("pattern", nargs="?")
    s = sub.add_parser("shot")
    s.add_argument("out")
    a = ap.parse_args()
    phone = Phone(a.serial)
    phone.require_connected()

    if a.cmd == "shot":
        png = phone.raw("exec-out", "screencap", "-p")
        if not png.startswith(b"\x89PNG"):
            raise SystemExit("screenshot failed: is the phone connected and unlocked?")
        with open(a.out, "wb") as fh:
            fh.write(png)
        print("saved " + a.out)
        return

    xml = ""
    for _ in range(3):  # uiautomator fails while the screen is animating; retry
        xml = phone.shell("uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 && cat /sdcard/ui.xml; rm -f /sdcard/ui.xml")
        if "<node" in xml:
            break
        time.sleep(1)
    else:
        raise SystemExit("Couldn't read the screen. Wake and unlock the phone, wait for it to settle, and try again.")
    pat = re.compile(a.pattern, re.I) if a.pattern else None
    for n in re.findall(r"<node [^>]*>", xml):
        t = re.search(r'text="([^"]*)"', n).group(1)
        d = re.search(r'content-desc="([^"]*)"', n).group(1)
        x1, y1, x2, y2 = map(int, re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n).groups())
        line = f"({(x1 + x2) // 2},{(y1 + y2) // 2}) {t!r} {d!r}"
        if (t or d) and (not pat or pat.search(line)):
            print(line)


if __name__ == "__main__":
    main()
