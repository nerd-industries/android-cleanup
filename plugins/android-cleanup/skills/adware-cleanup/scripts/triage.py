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


# Installers whose apps count as coming from a store. Anything else (no installer, the system
# package installer, a browser, a messenger, a file manager) means the APK was sideloaded.
STORES = {"com.android.vending": "Play Store", "com.sec.android.app.samsungapps": "Galaxy Store",
          "com.amazon.venezia": "Amazon Appstore", "com.huawei.appmarket": "AppGallery"}
TRANSFER = {"com.sec.android.easyMover": "Smart Switch transfer", "com.google.android.apps.restore": "Google restore"}
CARRIER = re.compile(r"^com\.(dti|att|tmobile|verizon|vzw|sprint|uscellular|motricity|ironsrc\.aura)\b")
JUNK_NAME = re.compile(r"clean|boost|junk|cooler|antivirus|virus|shield|guard|battery|flashlight|torch|"
                       r"applock|qrcode|qrscan|wallpaper|weather|launcher|optimi[sz]|speed|phonemaster|"
                       r"vpn|antispy|phonecare|ramclean|cpucool", re.I)
BROWSERS = {"com.android.chrome": "Chrome", "com.sec.android.app.sbrowser": "Samsung Internet",
            "org.mozilla.firefox": "Firefox", "org.mozilla.firefox_beta": "Firefox Beta",
            "org.mozilla.focus": "Firefox Focus", "com.microsoft.emmx": "Edge", "com.brave.browser": "Brave",
            "com.opera.browser": "Opera", "com.opera.mini.native": "Opera Mini", "com.opera.gx": "Opera GX",
            "com.duckduckgo.mobile.android": "DuckDuckGo", "com.vivaldi.browser": "Vivaldi",
            "com.kiwibrowser.browser": "Kiwi", "com.UCMobile.intl": "UC Browser", "mark.via.gp": "Via",
            "com.chrome.beta": "Chrome Beta", "com.google.android.googlequicksearchbox": None}
PKG = r"[a-zA-Z][\w]*(?:\.[\w]+)+"


def install_source(installer):
    """(label, sideloaded?) for an installer package name."""
    if installer in STORES:
        return STORES[installer], False
    if installer in TRANSFER:
        return TRANSFER[installer], False
    if CARRIER.match(installer or ""):
        return "carrier preload", False
    if installer in ("null", "", None):
        return "SIDELOADED (no installer)", True
    return f"SIDELOADED via {installer}", True


def package_details(dump):
    """Per package: firstInstallTime, lastUpdateTime, and granted permission names."""
    info, cur = {}, None
    for line in dump.splitlines():
        m = re.match(r"\s*Package \[([^\]]+)\]", line)
        if m:
            cur = m.group(1)
            info.setdefault(cur, {"perms": set()})
            continue
        if not cur:
            continue
        for key in ("firstInstallTime", "lastUpdateTime"):
            m = re.search(key + r"=(\S+ \S+)", line)
            if m and key not in info[cur]:
                info[cur][key] = m.group(1)
        m = re.match(r"\s*([\w.]+): granted=true", line)
        if m:
            info[cur]["perms"].add(m.group(1))
    return info


def app_usage(usage):
    """Per package: (latest lastTimeUsed, highest appLaunchCount) across all usage-stats intervals."""
    out = {}
    for m in re.finditer(r'package=(\S+) totalTimeUsed="[^"]*" lastTimeUsed="([^"]+)"(.*)', usage):
        pkg, last, rest = m.group(1), m.group(2), m.group(3)
        launches = int(re.search(r"appLaunchCount=(\d+)", rest).group(1)) if "appLaunchCount=" in rest else 0
        prev_last, prev_launch = out.get(pkg, ("", 0))
        out[pkg] = (max(prev_last, last if not last.startswith("19") else ""), max(prev_launch, launches))
    return out


def packages_in(text):
    return set(re.findall(PKG + r"(?=/|:|\s|$)", text or ""))


def suspect_apps(dump, listing, usage, today, access, launcher_pkgs):
    """Third-party apps scored on adware red flags, highest first: (score, package, source, reasons).
    access maps a label ("draws over other apps", ...) to the set of packages holding that access."""
    details, used = package_details(dump), app_usage(usage)
    rows = []
    for line in listing.splitlines():
        m = re.match(r"package:(\S+)\s+installer=(\S+)", line.strip())
        if not m:
            continue
        pkg, installer = m.groups()
        source, sideloaded = install_source(installer)
        d = details.get(pkg, {"perms": set()})
        first = (d.get("firstInstallTime") or "")[:10]
        if sideloaded and (first[:4] < "2010" or pkg.startswith(("com.samsung.", "com.sec."))):
            source, sideloaded = "factory preinstalled", False  # factory image apps carry a 2008/2009 stamp
        score, why = 0, []
        if pkg.startswith("org.chromium.webapk."):
            score += 2
            why.append("a website installed as an app (WebAPK): find which site in its app info")
        if sideloaded:
            score += 4
            why.append("not from an app store (sideloaded, patched or cracked apps land here)")
        for label, pkgs in access.items():
            if pkg in pkgs:
                weight = 3 if label in ("device admin", "accessibility service") else 1
                score += weight
                why.append(label)
        if launcher_pkgs and pkg not in launcher_pkgs:
            score += 2
            why.append("no app icon (hidden from the app drawer)")
        last_update = (d.get("lastUpdateTime") or "")[:10]
        last_used, launches = used.get(pkg, ("", 0))
        try:
            age = (today - dt.date.fromisoformat(first)).days
        except ValueError:
            age = None
        if age is not None and age > 3 and not last_used and launches == 0:
            score += 1
            why.append("never opened in the usage history")
        if age is not None and age <= 30:
            score += 1
            why.append(f"installed {first}")
        try:
            if (today - dt.date.fromisoformat(last_update)).days > 730:
                score += 1
                why.append(f"not updated since {last_update} (abandoned)")
        except ValueError:
            pass
        if JUNK_NAME.search(pkg):
            score += 1
            why.append("cleaner/booster/VPN-type utility name (a common adware disguise)")
        if "android.permission.REQUEST_INSTALL_PACKAGES" in d["perms"] or pkg in access.get("_install", set()):
            score += 1
            why.append("can install other apps")
        rows.append((score, pkg, source, [w for w in why]))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return rows


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
    ap.add_argument("--all", action="store_true", help="list every third-party app with its score")
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

    overlays = phone.shell("appops query-op SYSTEM_ALERT_WINDOW allow").strip()
    admins = sorted(set(re.findall(r"ComponentInfo\{[^}]+\}", phone.shell("dumpsys device_policy"))))
    a11y = phone.shell("settings get secure enabled_accessibility_services").strip()
    listeners = phone.shell("settings get secure enabled_notification_listeners").strip()
    roles = phone.shell("cmd role get-role-holders android.app.role.HOME; "
                        "cmd role get-role-holders android.app.role.BROWSER").strip()
    installers = phone.shell("appops query-op REQUEST_INSTALL_PACKAGES allow").strip()
    print("== DRAW OVER OTHER APPS (SYSTEM_ALERT_WINDOW allowed)")
    print(overlays)
    print("== DEVICE ADMINS")
    print("\n".join(admins))
    print("== ACCESSIBILITY SERVICES")
    print(a11y)
    print("== NOTIFICATION LISTENERS")
    print(listeners.replace(":", "\n"))
    print("== DEFAULT HOME / BROWSER")
    print(roles)

    launcher = packages_in(phone.shell("cmd package query-activities --brief -a android.intent.action.MAIN "
                                       "-c android.intent.category.LAUNCHER"))
    if len(launcher) < 5:  # query unsupported on this Android version: skip the hidden-icon check
        launcher = set()
    phone_date = phone.shell("date +%F").strip()  # the phone's clock, not the PC's
    today = dt.date.fromisoformat(phone_date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", phone_date) else dt.date.today()
    access = {"draws over other apps": packages_in(overlays), "device admin": packages_in(" ".join(admins)),
              "accessibility service": packages_in(a11y), "reads notifications": packages_in(listeners),
              "_install": packages_in(installers)}
    rows = suspect_apps(text["packages.txt"], text["third-party.txt"], text["usage.txt"], today, access, launcher)
    sideloaded = [r for r in rows if r[2].startswith("SIDELOADED")]
    print("== SUSPECT APPS, MOST SUSPICIOUS FIRST (score | package | install source | red flags)")
    print("   Sideloaded apps are top suspects: recommend removing every one the customer can't vouch for.")
    print("   Store, carrier and Smart Switch apps are trusted sources, but still check the flags.")
    if not launcher:
        print("   (hidden-icon check skipped: this Android version can't list launcher icons over adb)")
    for score, pkg, source, why in [r for r in rows if r[0] >= 3 or a.all]:
        print(f"{score:>2} | {pkg} | {source} | {'; '.join(why)}")
    print(f"   {len(sideloaded)} sideloaded app(s); {sum(1 for r in rows if r[0] < 3)} other app(s) scored below 3 "
          f"(weak or no red flags; full scores: rerun with --all).")

    print("== BROWSERS INSTALLED (clear site notifications in every one)")
    third_party = {r[1] for r in rows}
    browsing = packages_in(phone.shell("cmd package query-activities --brief -a android.intent.action.VIEW "
                                       "-c android.intent.category.BROWSABLE -d http://example.com"))
    installed = set(re.findall(r"package:(\S+)", phone.shell("pm list packages")))
    for pkg in sorted((set(BROWSERS) & installed) | (browsing & third_party)):
        if BROWSERS.get(pkg, pkg) is not None:
            print(f"{BROWSERS.get(pkg, pkg)} ({pkg})")

    print("== BROWSER SITE NOTIFICATION CHANNELS, NEWEST FIRST (date granted | site)")
    print("   Chrome-based browsers only. Android keeps a channel after the site is blocked, so confirm in the browser.")
    for day, host in site_channels(text["notif.txt"]):
        print(day, host)

    print("== USAGE EVENTS (last 2 days): ad screens, browser launches, suspects")
    days = [str(today - dt.timedelta(d)) for d in range(2)]
    for e in usage_events.interesting(usage_events.events(out / "usage.txt", days)):
        print(" ".join(e))


if __name__ == "__main__":
    main()
