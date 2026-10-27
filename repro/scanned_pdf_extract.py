"""Tavily item 6: Extract returns the letterhead of a scanned PDF but not the image-only rates.

    TAVILY_API_KEY=... python repro/scanned_pdf_extract.py      # 1 credit (basic depth)

Extracts one scanned dairy rate-list PDF and prints how much text came back and whether any flag says the page is
image-only. Open the PDF yourself to see the rates are there as a picture. The file may have been replaced since.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

MAX_CREDITS = 2
URL = "https://www.gokulmilk.coop/uploads/milk_prices/milk_rates_english_wef_11_08_2026.pdf"


def main():
    resp = C.call("/extract", {"urls": [URL], "extract_depth": "basic", "include_usage": True}, estimate=1)
    got = (resp.get("results") or [{}])[0]
    text = got.get("raw_content") or ""
    print(f"url: {URL}")
    print(f"result keys: {sorted(got)}; failed_results: {resp.get('failed_results')!r}")
    print(f"{len(text)} characters of text; digits in the text: {sum(c.isdigit() for c in text)}")
    print(f"start of text: {text[:200]!r}")
    print("a flag for image-only pages is present: "
          f"{any(k in got for k in ('image_only', 'ocr', 'is_scanned', 'warning'))}")


if __name__ == "__main__":
    C.run(main)
