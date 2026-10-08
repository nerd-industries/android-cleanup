---
name: adware-cleanup
description: Use when a customer's Android or Samsung Galaxy phone connected over adb (USB debugging) shows pop-ups, adware, scam websites opening by themselves, fake virus or weather alerts, or unwanted ads outside apps, or when asked to check Samsung Modes and Routines for anything suspicious, or to write a printable phone cleanup report for the customer.
---

# Android Adware Cleanup (adb)

## Overview
On modern Android the "adware" is usually **not an app**. Check these three sources, in order of how often they cause pop-ups:
1. **Malicious Samsung Routine.** A routine disguised as a preset (e.g. "Playing games while charging") whose action is **Go to website**, often hidden behind date conditions.
2. **Browser site notifications.** Spam sites (fake weather or package alerts, random subdomains) that were allowed to send notifications.
3. **Apps.** Draw-over-apps, device-admin or accessibility abuse, or junk utilities.

The phone is the customer's. Investigate read-only first. **Get the tech's OK before uninstalling apps.** Ask which apps the customer actually uses. Ads that stay inside a game they play are normal, so leave those apps installed.

## Setup (works on Windows, macOS and Linux)
- **Python:** on Windows run scripts with `py -3 -I` (or `python -I`); on macOS/Linux use `python3 -I`. Written as `PY` below. The scripts need only the standard library.
- **adb:** the scripts find it on PATH or in the usual platform-tools folders. `PY scripts/adbtools.py` prints the path they found. If `adb` isn't on PATH, use that full path for your own adb commands (in PowerShell: `& "C:\path\adb.exe" -s X ...`). If nothing is found, ask the tech where platform-tools is and set `ADB` to the full path.
- **Phone:** run `adb devices`. `unauthorized` means the tech must tap **Allow** on the phone's USB debugging prompt. Empty means USB debugging is off, or the cable is charge-only.
- Pass the serial to every command: `--serial <serial>` for scripts and `adb -s <serial>` for adb. Never use `ANDROID_SERIAL=X cmd`, because that fails in PowerShell.
- Scripts are in this skill's `scripts/` and `report/` folders. Use their full paths. Put dumps and screenshots in a scratch folder, not in the skill folder.
- **First run:** if `~/.claude/android-cleanup/shop.json` doesn't exist, ask the tech for the shop details (see Report, step 1) at the start, while triage runs, so the job doesn't stall at the end.

## Workflow
1. **Triage (read-only):** `PY scripts/triage.py --serial X <scratch>/triage`. It reports device info, apps newest-first, overlay apps, device admins, accessibility services, notification listeners, browser site-notification channels with the date each was granted, and recent ad and browser events.
2. **Find the pop-up's trigger:** `PY scripts/usage_events.py <scratch>/triage/usage.txt --date YYYY-MM-DD --around HH:MM`. A browser launching right after a `com.android.systemui` NOTIFICATION_INTERRUPTION, with no app in the foreground, points to a **Routine**. A browser launching right after an ad screen means someone clicked an in-game ad, which is benign.
3. **Routines:** the app has no launcher icon, so open it with `adb -s X shell am start -a com.samsung.android.app.routines.action.LAUNCH_ROUTINE_TAB -p com.samsung.android.app.routines`. Routine data can't be read over adb, so open each routine and screenshot it, scrolling to the end of the **Then** list. Delete any routine with **Go to website**, **Open app**, or date/"Get details from data" logic that the customer didn't create (Delete → confirm Delete). Check the **Modes** tab for custom modes too.
4. **Chrome site notifications:** go to Chrome ⋮ → Settings → Site settings → Notifications and expand **Allowed**. Android keeps a site's channel after Chrome blocks it, so the triage list overstates what's live. To remove a site, go to Site settings → **All sites** → Search → trash icon → **Delete & reset**. Do this for every spam site, including recently added ones and the site the customer was on when the pop-up appeared. Then select **"Don't allow sites to send notifications"**. Also check Samsung Internet if it's installed.
5. **Apps:** `adb -s X uninstall <pkg>` only for apps the tech approved. Re-check with `adb -s X shell pm list packages -3`.

## Driving the screen
- Wake the screen first with `adb -s X shell input keyevent KEYCODE_WAKEUP`. If the screenshot shows the lock screen, ask the tech to unlock the phone.
- Screenshot: `PY scripts/ui.py --serial X shot <scratch>/s.png`, then Read it. Don't redirect `adb exec-out screencap` with `>`, because PowerShell corrupts the PNG. The image is shown scaled, so multiply coordinates by the factor noted with the image.
- Tap targets: `PY scripts/ui.py --serial X find "pattern"` prints `(x,y)` in real pixels. Tap with `adb -s X shell input tap x y`. Type with `adb -s X shell input text word`, sending spaces as `%s`.
- Finish on the home screen: `adb -s X shell input keyevent HOME`.

## Report (printable, black and white)
1. **Shop details:** the first time, ask the tech for the shop name, a short tagline, the address line, the phone/website line and the logo file. Save them to `~/.claude/android-cleanup/shop.json` (in the home folder, not the skill folder, so updates keep it) in the format of `report/shop-example.json`. Copy the logo next to it. `make_report.py` says so if it's missing.
2. Copy `report/example-data.json` to the scratch folder and fill it in with **only what you verified**. Never invent app names: if you couldn't confirm a label, use the package in backticks. Leave Customer as `""` so it prints as a write-in line, unless you know the name. Cell text supports `**bold**` and `` `mono` ``.
3. `PY report/make_report.py data.json Phone-Cleanup-Report-YYYY-MM-DD.pdf`, with the PDF in the folder Claude was started in (the job folder). It prints with Chrome or Edge and fails unless the PDF is exactly one page.
4. Read the PDF to check it before handing it over. Keep it pure black on white: no colors or gray fills.
5. Offer to open it for printing: `start "" "<pdf>"` on Windows (`Start-Process "<pdf>"` in PowerShell), `open "<pdf>"` on macOS.

## Common mistakes
| Mistake | Fix |
|---|---|
| Blaming the free games with heavy in-app ads | Inside-app ads are normal. Look for pop-ups *outside* apps. |
| Stopping at the app list | Routines and site notifications are the usual cause, so always check both. |
| Treating every `web:` channel as active | Confirm in Chrome's Allowed list. Most may already be blocked. |
| Uninstalling without asking | Confirm the list with the tech first. |
| Uninstall fails with `DELETE_FAILED_DEVICE_POLICY_MANAGER` | The app is a device admin. Turn it off in Settings → Security and privacy → Other security settings → Device admin apps, then uninstall again. |
| adb keeps dropping, or the device shows `offline` | Bad cable or port. Ask for a different data cable, plugged straight into the computer instead of a hub. |
