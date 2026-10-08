"""Print app activity from a `dumpsys usagestats` dump to find what showed a pop-up and when.
Usage: python usage_events.py usage.txt [--days N] [--date YYYY-MM-DD] [--interesting] [--around HH:MM]
  --interesting  only ad-SDK screens, browser launches and non-launcher notification events
  --around HH:MM every event within 3 minutes of that time (use with --date) to see what triggered it
"""
import argparse
import datetime as dt
import re
import sys

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except AttributeError:
        pass

AD_HINTS = re.compile(r"ads?\b|Ad(Activity|View)|Interstitial|Fullscreen|applovin|inmobi|bigo|fyber|"
                      r"mbridge|vungle|unity3d\.ads|ironsource|pangle|bytedance|chartboost", re.I)
BROWSERS = ("com.android.chrome", "com.sec.android.app.sbrowser", "org.mozilla.firefox",
            "com.microsoft.emmx", "com.opera.browser", "com.brave.browser")
TYPES = {"ACTIVITY_RESUMED", "NOTIFICATION_INTERRUPTION", "FOREGROUND_SERVICE_START"}


def events(path, dates):
    seen, out = set(), []
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.search(r'time="(\S+ \S+)" type=(\w+) package=(\S+)(?: class=(\S+))?', line)
        if not m or m.group(2) not in TYPES or m.group(1)[:10] not in dates:
            continue
        key = (m.group(1)[:19], m.group(2), m.group(3), m.group(4) or "")
        if key not in seen:
            seen.add(key)
            out.append(key)
    return sorted(out)


def interesting(evts):
    return [e for e in evts if (e[1] == "ACTIVITY_RESUMED" and (AD_HINTS.search(e[3]) or e[2] in BROWSERS))
            or (e[1] == "NOTIFICATION_INTERRUPTION" and e[2] == "com.android.systemui")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--date")
    ap.add_argument("--interesting", action="store_true")
    ap.add_argument("--around")
    a = ap.parse_args()

    dates = [a.date] if a.date else [str(dt.date.today() - dt.timedelta(d)) for d in range(a.days)]
    out = events(a.dump, dates)
    if a.around:
        center = dt.datetime.strptime(f"{dates[0]} {a.around}", "%Y-%m-%d %H:%M")
        out = [e for e in out if abs((dt.datetime.strptime(e[0], "%Y-%m-%d %H:%M:%S") - center).total_seconds()) <= 180]
    elif a.interesting:
        out = interesting(out)
    for e in out:
        print(" ".join(e))


if __name__ == "__main__":
    main()
