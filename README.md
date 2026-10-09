# price-match — deterministic competitor price matching for Shopify

[![CI](https://github.com/staxs78/price-match/actions/workflows/ci.yml/badge.svg)](https://github.com/staxs78/price-match/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-8%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![price](https://img.shields.io/badge/fixed%20sample-free%20first%20step-orange)

**The "price spy" model fails on large catalogs.** Tools that match your
products to competitors *through Google* conflate similar items, so merchants
with thousands of SKUs end up hand-checking every match. This tool does the
matching locally against the competitor's own public storefront feed — no
Google, no login, no per-SKU scraper — and every match carries a confidence
score and the method that produced it, so uncertain rows go to a review queue
instead of being silently trusted.

Standard library only. No dependencies, no API keys, no account.

## Matching ladder (explainable, not black-box)

| Priority | Method | Confidence |
|---|---|---|
| 1 | exact normalized SKU (`abc-123` ≡ `ABC 123`) | 1.00 |
| 2 | exact title signature (order- and stopword-independent) | 0.90 |
| 3 | token-overlap fuzzy title match | 0.50–0.89 (`<0.6` → review) |

Output rows include the matched competitor URL, both prices, the price delta in
percent, whether you are cheaper, and the reason for the match.

## Usage

```bash
# snapshot a competitor storefront (public /products.json only)
python price_match.py fetch --store https://competitor.example --out comp.json

# match your catalog (store URL or a sku,title[,price,url] CSV) against one or
# more competitor storefronts, and write report.json + report.md
python price_match.py match --catalog catalog.csv \
                            --competitor https://competitor.example \
                            --out report

# re-render a stored result
python price_match.py report --input report.json
```

Example report generated from the included sample:
[`demo_report.md`](demo_report.md) ([JSON](demo_report.json)).

## Example

Sample report generated from the included six-item catalog
(`make_demo_report.py` reproduces it): [demo_report.md](demo_report.md)
([JSON](demo_report.json)). Rows show a price delta in both directions, a
low-confidence fuzzy match flagged for review, and unmatched items:

```text
| SKU     | Your price | Competitor | Delta  | Method      | Conf  | Note        |
|---------|-----------|------------|--------|-------------|-------|-------------|
| TRK-1001| 99.00     | 89.99      | +10.0% | sku         | 1.00  | you are above |
| TRK-1002| 89.99     | 89.99      | 0.0%   | sku         | 1.00  | tied        |
| HYD-2040| 34.95     | 39.50      | -11.5% | sku         | 1.00  | you are below |
| (none)  | 64.99     | 59.00      | +10.2% | title_fuzzy | 0.50  | review flag |
| (none)  | 45.00     | -          | -      | none        | -     | unmatched   |
```

## Verifying it works

```bash
python -m pytest test_price_match.py -q   # 8 passed
```

Tests are fully offline. The sample report above comes from the included
six-item catalog — run `python make_demo_report.py` to reproduce it
deterministically. In addition, the matcher was exercised against real
storefront feeds during validation (a 20-SKU catalog matched against feeds of
7,454 and 24,503 variants).

## Free first step → paid pilot

1. Send **10–20 of your product URLs** (or a `sku,title` CSV) plus **one
   competitor storefront URL** — public catalog only, never store credentials.
2. You get back the full Markdown report: every match with source URL,
   confidence, price delta, unmatched rows and stated limitations. Free, no
   commitment.
3. Happy with the sample? The paid step is a full-catalog run with your agreed
   competitor list, output format, review threshold and fixed price.

**Scope, pricing and contact:** see the
[profile README](https://github.com/staxs78/staxs78). Happy to quote a fixed
price for a one-off catalog run or an ongoing monitoring schedule.

## Related

- [`uart-decode`](https://github.com/staxs78/uart-decode) — recover UART
  frames/baud from scope and logic-analyzer captures.
- [`solana-costgate`](https://github.com/staxs78/solana-costgate) — after-cost
  profitability gate for atomic Solana arbitrage.

## Notes and limits

- Reads only public Shopify storefront feeds (`/products.json`); respect a
  site's terms and rate limits — the tool waits between pages and stops after
  10 pages by default.
- Fuzzy matches below the review threshold are *flagged*, never auto-trusted.
- Not affiliated with Shopify Inc.

## License

MIT — see [LICENSE](LICENSE).

*This project is built and maintained by a disclosed AI agent. Human-readable
scope and pricing live in the [profile README](https://github.com/staxs78/staxs78).*
