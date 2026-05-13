# Paul Graham essay corpus

Local research corpus for the [`voice` skill](../../skills/voice/) — used to extract Paul Graham's writing voice into era-specific profiles (`pg-early`, `pg-startup`, `pg-late`).

The essay text itself is **not** checked in: PG's essays are copyrighted, and we don't redistribute them. The `_fetch_pg.py` script below pulls them from `paulgraham.com` on demand into this directory. The text files are gitignored.

## Regenerate the corpus locally

```bash
cd corpus/pg-essays
python3 _fetch_pg.py < _slugs.txt
```

Requires Python 3.9+. Uses only the standard library. Fetches in parallel with a ThreadPoolExecutor (12 workers). Takes about 60 seconds end-to-end and produces 229 `.txt` files (one per essay), ~3.5 MB total.

If `_slugs.txt` is missing or stale (PG publishes new essays periodically), regenerate it from `https://www.paulgraham.com/articles.html` — each essay link has the form `<a href="slug.html">`. A small script that does this is left as an exercise; the slug list is easy to scrape and only grows by a handful of entries per year.

## Files

| File                 | Purpose                                                                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `_fetch_pg.py`       | Fetches and HTML-strips all essays listed on stdin. Checked in.                                                                          |
| `_slugs.txt`         | Newline-separated list of essay slugs (`brandage.html`, etc). Checked in. Regenerate from `https://www.paulgraham.com/articles.html` if stale. |
| `<slug>.txt`         | One per essay, plain text. Gitignored.                                                                                                   |

## Why local?

Voice extraction needs the *actual text* — paraphrases or training-data recall produce unreliable calibration anchors. The corpus is downloaded once and read by hand or via Read-tool sub-agents working off these files.

## Provenance / licensing

All essays are © Paul Graham (paulgraham.com). They're used here transformatively to extract structural and rhythmic voice patterns for the `voice` skill's `pg-early.md`, `pg-startup.md`, and `pg-late.md` profiles. The profiles themselves quote only short verbatim passages as calibration anchors (typical "fair use" research/criticism territory). The corpus itself is kept local and is not redistributed.
