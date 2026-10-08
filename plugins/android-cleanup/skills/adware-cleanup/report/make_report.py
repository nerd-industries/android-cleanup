"""Build the printable one-page phone cleanup report (HTML and PDF) with the shop's own branding.

Usage: python make_report.py data.json Phone-Cleanup-Report.pdf
  Shop details come from ~/.claude/android-cleanup/shop.json (see shop-example.json).
  Writes the .html next to the .pdf, prints it with Chrome or Edge, and checks it is one page.

Pure black on white for B&W printing. A fit script shrinks the base font until everything fits the
fixed 7in x 9.6in sheet, so it is always one US Letter page.
"""
import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except AttributeError:
        pass

SHOP_FILE = Path.home() / ".claude" / "android-cleanup" / "shop.json"
HERE = Path(__file__).resolve().parent


def esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def md(v):
    """Light inline markup for cell text: **bold** and `mono`. Everything else is escaped."""
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(v))
    return re.sub(r"`(.+?)`", r'<span class="mono">\1</span>', s)


def table(columns, rows):
    if not rows:
        return ""
    cols = "".join(f'<col style="width:{c.get("width", "auto")}">' for c in columns)
    head = "".join(f"<th>{esc(c['label'])}</th>" for c in columns)
    body = "\n".join("<tr>" + "".join(
        f'<td class="{"bold" if c.get("bold") else ""}">{md(r[i]) if i < len(r) and r[i] else "&mdash;"}</td>'
        for i, c in enumerate(columns)) + "</tr>" for r in rows)
    return f"<table><colgroup>{cols}</colgroup><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def section(title, body):
    return f'<div class="section"><div class="section-title">{esc(title)}</div>{body}</div>' if body else ""


def logo_tag(shop):
    path = shop.get("logo")
    if not path:
        return ""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = SHOP_FILE.parent / p
    if not p.is_file():
        print(f"warning: logo {p} not found, printing without it", file=sys.stderr)
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    data = base64.b64encode(p.read_bytes()).decode()
    return f'<img src="data:{mime};base64,{data}" alt="" class="logo" />'


def build_html(d, shop):
    info = "".join(
        f'<div class="info-cell"><div class="info-label">{esc(k)}</div><div class="info-value">'
        f'{md(v) if v else "<span class=blank></span>"}</div></div>' for k, v in d.get("info", []))
    footer = [shop.get("address", ""), shop.get("contact", "")]
    advice = ""
    if d.get("advice"):
        items = "".join(f"<li>{md(a)}</li>" for a in d["advice"])
        advice = (f'<div class="notice"><div class="notice-badge">{esc(d.get("adviceBadge", "How to stay safe"))}</div>'
                  f'<ul class="notice-list">{items}</ul></div>')
    result = ""
    if d.get("result"):
        result = (f'<div class="result"><div class="notice-badge">{esc(d.get("resultBadge", "Result"))}</div>'
                  f'<div class="result-text">{md(d["result"])}</div></div>')
    tagline = f'<div class="brand-tagline">{esc(shop["tagline"])}</div>' if shop.get("tagline") else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(d.get("title", "Phone Cleanup Report"))}</title>
<style>
  @page {{ size: letter; margin: 0.5in 0.6in; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ background: #fff; color: #000; }}
  body {{ font-family: Arial, Helvetica, sans-serif; line-height: 1.3; }}
  @media screen {{ body {{ padding: 12px; }} }}
  .sheet {{ width: 7in; height: 9.6in; overflow: hidden; display: flex; flex-direction: column;
    font-size: var(--base, 10pt); -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  @media print {{ body {{ padding: 0; }} .sheet {{ margin: 0 auto; break-inside: avoid; }} }}

  .header {{ display: flex; align-items: center; justify-content: space-between; flex: none;
    padding-bottom: 10pt; border-bottom: 3pt solid #000; margin-bottom: 12pt; }}
  .brand {{ display: flex; align-items: center; gap: 10pt; }}
  .logo {{ width: 44pt; height: 44pt; object-fit: contain; }}
  .brand-name {{ font-size: 16pt; font-weight: 700; white-space: nowrap; }}
  .brand-tagline {{ font-size: 8pt; text-transform: uppercase; letter-spacing: 1.5pt; white-space: nowrap; }}
  .doc-info {{ text-align: right; }}
  .doc-title {{ font-size: 14pt; font-weight: 700; text-transform: uppercase; letter-spacing: 1pt; white-space: nowrap; }}
  .doc-date {{ font-size: 9pt; margin-top: 3pt; white-space: nowrap; }}

  .body {{ flex: 1 1 auto; min-height: 0; overflow: hidden; display: flex; flex-direction: column; gap: 1.15em; }}

  .info {{ display: flex; border: 1.5pt solid #000; flex: none; }}
  .info-cell {{ flex: 1 1 auto; padding: 0.45em 0.8em; border-right: 1.5pt solid #000; min-width: 0; }}
  .info-cell:last-child {{ border-right: none; flex-grow: 1.6; }}
  .info-label {{ font-size: 0.72em; font-weight: 700; text-transform: uppercase; letter-spacing: 1pt; }}
  .info-value {{ font-size: 1em; margin-top: 0.15em; white-space: nowrap; overflow: hidden; }}
  .blank {{ display: inline-block; width: 100%; border-bottom: 1pt solid #000; height: 1.05em; }}

  .section-title {{ font-size: 1.05em; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5pt;
    margin-bottom: 0.4em; }}
  table {{ width: 100%; table-layout: fixed; border-collapse: collapse; }}
  th {{ background: #000; color: #fff; text-align: left; padding: 0.38em 0.7em; font-size: 0.85em;
    font-weight: 700; text-transform: uppercase; letter-spacing: 1pt; }}
  td {{ padding: 0.42em 0.7em; border-bottom: 1pt solid #000; vertical-align: top; }}
  td.bold {{ font-weight: 700; }}
  .mono {{ font-family: Consolas, "Courier New", monospace; font-size: 0.92em; letter-spacing: 0.02em; }}

  .result {{ border: 3pt solid #000; padding: 1.25em 1.1em 0.85em; position: relative; margin-top: 0.4em; flex: none; }}
  .notice {{ border: 3pt solid #000; padding: 1.3em 1.1em 0.75em; position: relative; margin-top: 0.6em; flex: none; }}
  .notice-badge {{ position: absolute; top: -0.85em; left: 1.1em; background: #000; color: #fff;
    padding: 0.25em 0.8em; font-size: 0.85em; font-weight: 700; text-transform: uppercase; letter-spacing: 2pt; }}
  .result-text {{ font-size: 1.05em; line-height: 1.4; }}
  .notice-list {{ padding-left: 1.2em; line-height: 1.4; }}
  .notice-list li {{ margin-bottom: 0.2em; }}

  .footer {{ flex: none; margin-top: 10pt; padding-top: 8pt; border-top: 1pt solid #000;
    display: flex; justify-content: space-between; font-size: 9pt; }}
</style></head>
<body>
<div class="sheet">
  <div class="header">
    <div class="brand">
      {logo_tag(shop)}
      <div><div class="brand-name">{esc(shop.get("name", ""))}</div>{tagline}</div>
    </div>
    <div class="doc-info"><div class="doc-title">{esc(d.get("title", "Phone Cleanup Report"))}</div><div class="doc-date">{esc(d.get("dateLabel", ""))}</div></div>
  </div>
  <div class="body">
    {f'<div class="info">{info}</div>' if info else ""}
    {result}
    {section("What we found and fixed", table([{"label": "Area", "bold": True, "width": "20%"}, {"label": "What we found", "width": "43%"}, {"label": "What we did"}], d.get("findings")))}
    {section("Apps removed", table([{"label": "App", "bold": True, "width": "34%"}, {"label": "Why it was removed"}], d.get("removed")))}
    {section("Checked - no problems found", table([{"label": "Check", "bold": True, "width": "34%"}, {"label": "Result"}], d.get("checked")))}
    {advice}
  </div>
  <div class="footer"><div>{esc(footer[0])}</div><div>{esc(footer[1])}</div></div>
</div>
<script>
(function () {{
  // Shrink the base font until the body fits the fixed sheet (one page guaranteed).
  var sheet = document.querySelector(".sheet"), body = sheet.querySelector(".body");
  var size = 12;
  function set() {{ sheet.style.setProperty("--base", size + "pt"); }}
  set();
  for (var i = 0; i < 80 && body.scrollHeight > body.clientHeight + 0.5 && size > 6; i++) {{ size -= 0.1; set(); }}
}})();
</script>
</body></html>"""


def find_browser():
    """Chrome, Edge, Chromium or Brave on Windows, macOS or Linux."""
    for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "microsoft-edge",
                 "msedge", "chrome", "brave-browser"):
        if shutil.which(name):
            return shutil.which(name)
    pf = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    candidates = [Path(p) / sub for p in pf if p for sub in (
        "Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe",
        "BraveSoftware/Brave-Browser/Application/brave.exe")]
    candidates += [Path("/Applications") / app for app in (
        "Google Chrome.app/Contents/MacOS/Google Chrome", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "Chromium.app/Contents/MacOS/Chromium", "Brave Browser.app/Contents/MacOS/Brave Browser")]
    for c in candidates:
        if c.is_file():
            return str(c)
    sys.exit("No Chrome or Edge found to print the PDF. Install Google Chrome, or open the .html and print it to PDF.")


def page_count(pdf):
    data = pdf.read_bytes()
    counts = [int(n) for n in re.findall(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", data)]
    counts += [int(n) for n in re.findall(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", data)]
    return max(counts) if counts else len(re.findall(rb"/Type\s*/Page\b", data))


def load_shop():
    if not SHOP_FILE.is_file():
        sys.exit(f"No shop details yet. Ask the tech for them, then save them to {SHOP_FILE} "
                 f"in the format of {HERE / 'shop-example.json'}.")
    return json.loads(SHOP_FILE.read_text(encoding="utf-8"))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    data_path, pdf_path = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    shop = load_shop()
    data = json.loads(data_path.read_text(encoding="utf-8"))
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(build_html(data, shop), encoding="utf-8")

    with tempfile.TemporaryDirectory() as profile:  # own profile, so an open browser window can't grab the job
        subprocess.run([find_browser(), "--headless", "--disable-gpu", "--no-sandbox", "--no-first-run",
                        f"--user-data-dir={profile}", "--no-pdf-header-footer", "--virtual-time-budget=5000",
                        f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                       capture_output=True, timeout=120)
    if not pdf_path.is_file():
        sys.exit(f"PDF was not created. Open {html_path} in a browser and print it to PDF instead.")
    pages = page_count(pdf_path)
    print(f"wrote {pdf_path} ({pages} page{'s' if pages != 1 else ''})")
    if pages != 1:
        sys.exit("ERROR: report is not one page. Shorten the text in the data file and run again.")


if __name__ == "__main__":
    main()
