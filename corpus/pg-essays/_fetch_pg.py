#!/usr/bin/env python3
"""Fetch and clean Paul Graham essays. Writes plain text to /tmp/pg_essays/<slug>.txt."""

import html
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT_DIR = Path("/tmp/pg_essays")
OUT_DIR.mkdir(exist_ok=True)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def clean(raw: str) -> str:
    raw = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.I)
    raw = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL | re.I)
    raw = re.sub(r"<head\b[^>]*>.*?</head>", "", raw, flags=re.DOTALL | re.I)
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</p>", "\n\n", raw, flags=re.I)
    raw = re.sub(r"<p\b[^>]*>", "\n\n", raw, flags=re.I)
    raw = re.sub(r"<li\b[^>]*>", "\n- ", raw, flags=re.I)
    raw = re.sub(r"</li>", "", raw, flags=re.I)
    raw = re.sub(r"<h[1-6][^>]*>", "\n\n# ", raw, flags=re.I)
    raw = re.sub(r"</h[1-6]>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    lines = [line.strip() for line in raw.splitlines()]
    return "\n".join(lines).strip()


def fetch_one(slug: str) -> tuple[str, str | None, int]:
    url = f"https://www.paulgraham.com/{slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        text = clean(raw)
        out_path = OUT_DIR / f"{slug.replace('.html', '').replace('.txt', '')}.txt"
        out_path.write_text(text, encoding="utf-8")
        return (slug, None, len(text))
    except Exception as e:
        return (slug, str(e), 0)


def main():
    slugs = [line.strip() for line in sys.stdin if line.strip()]
    print(f"Fetching {len(slugs)} essays with 12 workers...")
    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(fetch_one, s): s for s in slugs}
        for fut in as_completed(futures):
            slug, err, size = fut.result()
            results.append((slug, err, size))
            status = f"ERR: {err}" if err else f"{size:,} chars"
            print(f"  {slug}: {status}")
    errs = [r for r in results if r[1]]
    print(f"\nDone. {len(results) - len(errs)} OK, {len(errs)} errors.")
    if errs:
        print("Failures:")
        for slug, err, _ in errs:
            print(f"  {slug}: {err}")


if __name__ == "__main__":
    main()
