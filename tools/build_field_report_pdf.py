#!/usr/bin/env python3
"""Print docs/field_report_for_tavily.md to docs/field_report_for_tavily.pdf (0 credits, standard library only).

    python tools/build_field_report_pdf.py

Converts the small Markdown subset the report uses (headings, paragraphs, numbered and bullet lists, tables, bold,
inline code) to HTML and prints it with headless Google Chrome. Run tools/sync_doc_numbers.py first.
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "field_report_for_tavily.md"
OUT = ROOT / "docs" / "field_report_for_tavily.pdf"
CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium"]
CSS = ("body{font:10pt/1.35 -apple-system,Helvetica,Arial,sans-serif;margin:0;color:#111}h1{font-size:16pt;margin:0 0 4pt}"
       "h2{font-size:11.5pt;margin:10pt 0 3pt;border-bottom:1px solid #ccc}p,ul,ol{margin:3pt 0}li{margin:2pt 0}"
       "code{font:8.5pt Menlo,monospace;background:#f2f2f2;padding:0 2px}table{border-collapse:collapse;width:100%;"
       "font-size:8.5pt}th,td{border:1px solid #bbb;padding:2px 4px;text-align:left;vertical-align:top}th{background:#eee}"
       "@page{size:A4;margin:14mm}")


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def convert(md):
    md = re.sub(r"<!--.*?-->\n?", "", md, flags=re.S)
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))])
                i += 1
            i -= 1
            head, body = rows[0], [r for r in rows[2:]]
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c.replace(chr(92) + '|', '|'))}</td>" for c in r)
                                 + "</tr>" for r in body) + "</table>")
        elif re.match(r"(\d+\.|-) ", ln):
            tag = "ol" if ln[0].isdigit() else "ul"
            items = []
            while i < len(lines) and re.match(r"(\d+\.|-) ", lines[i]):
                items.append(inline(re.sub(r"^(\d+\.|-) ", "", lines[i])))
                i += 1
            i -= 1
            out.append(f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out)


def main():
    page = f"<!doctype html><meta charset=utf-8><style>{CSS}</style>{convert(SRC.read_text(encoding='utf-8'))}"
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "report.html"
        src.write_text(page, encoding="utf-8")
        for chrome in CHROME:
            try:
                subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                                f"--print-to-pdf={OUT}", src.as_uri()], check=True, capture_output=True, timeout=90)
                break
            except FileNotFoundError:
                continue
        else:
            sys.exit("no Chrome or Chromium found to print the PDF")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
