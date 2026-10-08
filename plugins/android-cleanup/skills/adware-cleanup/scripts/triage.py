"""Read-only adware triage for an adb-connected Android phone. Changes nothing on the device.
Usage: python triage.py --serial <serial> <out-dir>
Writes raw dumps to <out-dir> and prints a summary.
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script folder
from adbtools import Phone, add_serial_arg
import usage_events


def packages_newest_first(dump, listing):
    """Rows of (first install, last update, installer, package) for third-party apps, newest first."""
    installer = {}
    for line in listing.splitlines():
        m = re.match(r"package:(\S+)\s+installer=(\S+)", line.strip())
        if m:
            installer[m.group(1)] = m.group(2)
    info, cur = {}, None
    for line in dump.splitlines():
        m = re.match(r"\s*Package \[([^\]]+)\]", line)
        if m:
            cur = m.group(1)
            info.setdefault(cur, {})
            continue
        if cur:
            for key in ("firstInstallTime", "lastUpdateTime"):
                m = re.search(key + r"=(\S+ \S+)", line)
                if m and key not in info[cur]:
                    info[cur][key] = m.group(1)
    rows = [(info.get(p, {}).get("firstInstallTime", "?"), info.get(p, {}).get("lastUpdateTime", "?"), inst, p)
            for p, inst in installer.items()]
    return sorted(rows, reverse=True)


def site_channels(notif):
    """Browser site-notification channels as (date granted, site), newest first."""
    found = set(re.findall(r"mId='web:https?://([^;']*);(\d+)'", notif))
    rows = []
    for host, stamp in found:
        # Chrome stores the grant time as microseconds since 1601-01-01 (Windows FILETIME epoch).
        when = dt.datetime.fromtimestamp(int(stamp) / 1_000_000 - 11644473600)
        rows.append((when.strftime("%Y-%m-%d"), host))
    return sorted(rows, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    add_serial_arg(ap)
    ap.add_argument("out")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    phone = Phone(a.serial)
    phone.require_connected()

    print("== DEVICE")
    print(phone.shell('echo "$(getprop ro.product.model) | Android $(getprop ro.build.version.release) | '
                      '$(getprop ro.build.display.id)"; date').strip())

    print(f"== RAW DUMPS -> {out}")
    dumps = {"packages.txt": "dumpsys package packages", "notif.txt": "dumpsys notification --noredact",
             "usage.txt": "dumpsys usagestats", "third-party.txt": "pm list packages -3 -i"}
    text = {}
    for name, command in dumps.items():
        text[name] = phone.shell(command)
        (out / name).write_text(text[name], encoding="utf-8")

    print("== THIRD-PARTY APPS, NEWEST FIRST (install date | last update | installer | package)")
    rows = packages_newest_first(text["packages.txt"], text["third-party.txt"])
    for first, last, inst, pkg in rows[:40]:
        print(f"{first[:16]} | {last[:16]} | {inst} | {pkg}")
    if len(rows) > 40:
        print(f"   ...{len(rows) - 40} more. Full list: {out / 'third-party.txt'}")

    print("== DRAW OVER OTHER APPS (SYSTEM_ALERT_WINDOW allowed)")
    print(phone.shell("appops query-op SYSTEM_ALERT_WINDOW allow").strip())
    print("== DEVICE ADMINS")
    for c in sorted(set(re.findall(r"ComponentInfo\{[^}]+\}", phone.shell("dumpsys device_policy")))):
        print(c)
    print("== ACCESSIBILITY SERVICES")
    print(phone.shell("settings get secure enabled_accessibility_services").strip())
    print("== NOTIFICATION LISTENERS")
    print(phone.shell("settings get secure enabled_notification_listeners").strip().replace(":", "\n"))
    print("== DEFAULT HOME / BROWSER")
    print(phone.shell("cmd role get-role-holders android.app.role.HOME; "
                      "cmd role get-role-holders android.app.role.BROWSER").strip())

    print("== BROWSER SITE NOTIFICATION CHANNELS, NEWEST FIRST (date granted | site)")
    print("   Android keeps a channel even after Chrome blocks the site. Confirm in Chrome > Site settings > Notifications.")
    for day, host in site_channels(text["notif.txt"]):
        print(day, host)

    print("== USAGE EVENTS (last 2 days): ad screens, browser launches, suspects")
    phone_date = phone.shell("date +%F").strip()  # the phone's clock, not the PC's
    today = dt.date.fromisoformat(phone_date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", phone_date) else dt.date.today()
    days = [str(today - dt.timedelta(d)) for d in range(2)]
    for e in usage_events.interesting(usage_events.events(out / "usage.txt", days)):
        print(" ".join(e))


if __name__ == "__main__":
    main()
