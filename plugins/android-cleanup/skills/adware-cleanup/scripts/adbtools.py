"""Shared helpers: find adb on Windows, macOS or Linux and run it against one phone."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; never crash on an odd app label.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except AttributeError:
        pass


def find_adb():
    """Return the adb executable, checking PATH first and then the usual install folders."""
    if os.environ.get("ADB") and Path(os.environ["ADB"]).is_file():
        return os.environ["ADB"]
    found = shutil.which("adb")
    if found:
        return found
    home = Path.home()
    exe = "adb.exe" if os.name == "nt" else "adb"
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local")) / "Android/Sdk/platform-tools",
        Path("C:/platform-tools"),
        Path("C:/Android/platform-tools"),
        home / "platform-tools",
        home / "Downloads/platform-tools",
        home / "Library/Android/sdk/platform-tools",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    for folder in candidates:
        if (folder / exe).is_file():
            return str(folder / exe)
    sys.exit("adb not found. Install Android platform-tools "
             "(https://developer.android.com/tools/releases/platform-tools), "
             "or set the ADB environment variable to the full path of adb.")


class Phone:
    def __init__(self, serial=None):
        self.adb = find_adb()
        self.serial = serial

    def _cmd(self, args):
        return [self.adb] + (["-s", self.serial] if self.serial else []) + list(args)

    def raw(self, *args):
        """Run an adb command and return its stdout as bytes. adb errors are shown, never swallowed."""
        r = subprocess.run(self._cmd(args), capture_output=True)
        if r.returncode != 0 and r.stderr.strip():
            print("adb error: " + r.stderr.decode("utf-8", errors="replace").strip(), file=sys.stderr)
        return r.stdout

    def require_connected(self):
        """Stop with a plain explanation unless exactly this phone is connected and authorized."""
        r = subprocess.run(self._cmd(["get-state"]), capture_output=True, text=True, errors="replace")
        state = (r.stdout or "").strip()
        if state == "device":
            return
        err = (r.stderr or "").strip()
        if "unauthorized" in err:
            sys.exit("Phone is unauthorized: unlock it and tap Allow on the 'Allow USB debugging?' prompt.")
        if "no permissions" in err or "insufficient permissions" in err:
            sys.exit("Linux USB permission problem: install your distro's adb udev rules "
                     "(Debian/Ubuntu: adb; Arch: android-udev), unplug and replug the phone, and try again.")
        if "more than one" in err:
            sys.exit("More than one phone connected: pass --serial (see `adb devices`).")
        sys.exit(f"Phone not ready ({state or err or 'not found'}). Check USB debugging is on and the cable carries data.")

    def shell(self, command):
        """Run one shell command string on the phone and return its text output."""
        return self.raw("shell", command).decode("utf-8", errors="replace").replace("\r\n", "\n")


def add_serial_arg(parser):
    parser.add_argument("--serial", "-s", help="phone serial from `adb devices` (needed if more than one is connected)")


if __name__ == "__main__":
    print(find_adb())  # full path to adb, for running adb commands directly
