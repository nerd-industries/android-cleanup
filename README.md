# Android Pop-up Cleanup for Claude Code

A Claude Code plugin for repair shops. Plug in a customer's Android or Samsung Galaxy phone that's showing pop-ups, scam websites or fake virus and weather alerts. Claude finds where they're coming from, walks you through removing them, and prints a one-page report for the customer with **your shop's** name, logo and address.

Built at [Nerdy Neighbor](https://nerdyneighbor.net) in Prescott, AZ, from real customer phones.

![Sample report](docs/sample-report.png)

## Why the usual "remove the bad app" approach misses it

On current Android the pop-ups usually **aren't an app at all**. The skill checks the three real sources, most common first:

1. **A hidden Samsung Routine.** A scam site adds a routine with an innocent name like "Playing games while charging" that opens a website whenever the phone charges. There's no app to uninstall, and antivirus apps don't see it.
2. **Chrome site notifications.** Fake "weather alert", "package delivery" or "virus found" sites that the customer once tapped **Allow** on.
3. **Apps.** Apps that draw over other apps, or abuse device admin or accessibility, plus junk "cleaner" and "booster" apps.

Everything starts **read-only**. Nothing is uninstalled until you approve it, and Claude asks which apps the customer actually uses. Free games that show ads *inside* the game are left alone.

## What you need

- **Claude Code** on a paid Claude plan (Pro or Max) or an API key: <https://claude.com/claude-code>
- **Python 3**
- **Android platform-tools (adb)**
- **Google Chrome or Microsoft Edge**, used to print the PDF report
- A USB **data** cable. Many cheap cables are charge-only.

### Windows
Open PowerShell and run:
```powershell
winget install Python.Python.3.12
winget install Google.PlatformTools
winget install Git.Git
irm https://claude.ai/install.ps1 | iex
```
Edge is already installed, so you don't need Chrome.

### macOS
```bash
brew install python android-platform-tools
curl -fsSL https://claude.ai/install.sh | bash
```
No Homebrew? Get it at <https://brew.sh>.

## Install the plugin
Start `claude` in a terminal, then type:
```
/plugin marketplace add nerd-industries/android-cleanup
/plugin install android-cleanup@android-cleanup
```
Restart Claude Code. To update later, run `/plugin marketplace update android-cleanup`.

## Using it

1. **On the phone:** Settings → About phone → Software information → tap **Build number** 7 times. Then go to Settings → Developer options → turn on **USB debugging**.
2. Plug the phone in and tap **Allow** on the "Allow USB debugging?" prompt.
3. Start `claude` in a folder for the job (for example `Documents\Cleanups\Smith`) and describe the problem:
   > Customer's Galaxy is plugged in. Pop-ups and a scam website keep opening by themselves, mostly when it's charging.
4. Claude runs the checks, shows you what it found, and asks before removing anything. Some steps happen on the phone's screen (Samsung doesn't allow reading Routines over USB), so keep the phone unlocked.
5. When it's done, ask for **the cleanup report**. The first time, Claude asks for your shop name, address, phone, website and logo, and remembers them.
6. Turn USB debugging back off before the customer leaves.

## Privacy

Everything runs on your computer and the phone. The plugin itself sends nothing anywhere. Claude Code sends what it reads (app lists, website names, screenshots of the phone's settings screens) to Anthropic to work on it, the same as any Claude Code session. Tell your customer, and don't use it on phones you're not authorized to service.

## License

MIT. Use it, change it, share it. No warranty: you're responsible for what's changed on a customer's phone.
