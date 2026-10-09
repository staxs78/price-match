#!/usr/bin/env python3
"""price_match.py — deterministic competitor price matching for Shopify catalogs.

Problem it solves: "Google-based" competitor matching (the Pricefy model)
conflates similar products and produces wrong matches, so merchants with large
catalogs end up hand-matching thousands of SKUs. This tool matches your catalog
variants to competitor storefronts using stable, explainable signals instead:

  1. exact normalized SKU  (score 1.00)
  2. exact title signature (score 0.90)
  3. high token overlap    (score 0.50-0.89, tunable)

It reads only the public storefront feed each Shopify theme already renders
(`/products.json`) - no login, no Google, no paid data. Every match carries a
confidence score and the reason, so low-confidence rows can be reviewed instead
of silently trusted.

Usage:
  python price_match.py match --catalog <store-url-or-csv> --competitor <url> [--competitor <url> ...]
  python price_match.py fetch  --store <url> --out <file.json>     # snapshot a storefront
  python price_match.py report --input <matches.json>

Exit 0 on success, 2 on bad input/network.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = "price-match/1.0 (deterministic catalog matching)"
MAX_PAGES, DELAY_S = 10, 1.0

_STOP = {
    "the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on",
    "by", "new", "pack", "set", "pcs", "pc", "x", "inch", "mm", "cm",
}


# ---------------------------------------------------------------- normalization
def norm_sku(value) -> str:
    """Uppercase, drop everything that is not a letter/digit."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def norm_tokens(title: str) -> list:
    """Lowercased significant word tokens (drops punctuation and stopwords)."""
    words = re.findall(r"[a-z0-9]+", str(title or "").lower())
    return [w for w in words if w not in _STOP and len(w) > 1]


def title_signature(title: str) -> str:
    """Order-independent signature: sorted significant tokens joined."""
    return " ".join(sorted(set(norm_tokens(title))))


def _rec_title(rec: dict) -> str:
    return rec.get("product_title") or rec.get("title", "") or ""


def _tokenset(rec: dict) -> set:
    return set(norm_tokens(_rec_title(rec))) | set(norm_tokens(rec.get("variant_title", "")))


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------- storefront IO
def _fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def origin_of(url: str) -> str:
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    from urllib.parse import urlsplit
    p = urlsplit(url)
    if not p.hostname:
        raise ValueError(f"bad url: {url}")
    return f"{p.scheme}://{p.hostname}"


def fetch_store(origin: str) -> list:
    """Return a list of variant records from a Shopify storefront feed."""
    origin = origin_of(origin)
    records = []
    for page in range(1, MAX_PAGES + 1):
        data = _fetch_json(f"{origin}/products.json?limit=250&page={page}")
        items = data.get("products", [])
        if not items:
            break
        for p in items:
            handle = p.get("handle", "")
            for v in p.get("variants", []):
                records.append({
                    "origin": origin,
                    "product_title": p.get("title", ""),
                    "variant_title": v.get("title", ""),
                    "sku": v.get("sku") or "",
                    "price": v.get("price", ""),
                    "compare_at": v.get("compare_at_price"),
                    "available": bool(v.get("available")),
                    "url": f"{origin}/products/{handle}" + (f"?variant={v['id']}" if v.get("id") else ""),
                })
        if len(items) < 250:
            break
        time.sleep(DELAY_S)
    if not records:
        raise ValueError(f"no products returned by {origin} (not a Shopify storefront?)")
    return records


def load_catalog(path_or_url: str) -> list:
    """Load catalog items from a storefront origin or a CSV (sku,title[,price,url])."""
    if os.path.exists(path_or_url):
        items = []
        with open(path_or_url, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                items.append({
                    "sku": row.get("sku", "") or "",
                    "title": row.get("title", "") or "",
                    "price": row.get("price", "") or "",
                    "url": row.get("url", "") or "",
                })
        if not items:
            raise ValueError(f"empty catalog CSV: {path_or_url}")
        return items
    return fetch_store(path_or_url)


# ---------------------------------------------------------------- index + match
def build_index(records: list) -> dict:
    sku_idx, sig_idx, all_recs = {}, {}, []
    for rec in records:
        idx = len(all_recs)
        all_recs.append(rec)
        sk = norm_sku(rec.get("sku"))
        if sk:
            sku_idx.setdefault(sk, []).append(idx)
        sig = title_signature(_rec_title(rec) + " " + rec.get("variant_title", ""))
        if sig:
            sig_idx.setdefault(sig, []).append(idx)
    return {"by_sku": sku_idx, "by_sig": sig_idx,
            "tokens": [_tokenset(r) for r in all_recs], "records": all_recs}


def _best_title_match(item_tokens: set, index: dict, min_overlap: float):
    best, best_score = None, 0.0
    for i, toks in enumerate(index["tokens"]):
        score = jaccard(item_tokens, toks)
        if score > best_score:
            best, best_score = i, score
    if best is not None and best_score >= min_overlap:
        return best, round(best_score, 3)
    return None, 0.0


def match_item(item: dict, index: dict, min_overlap: float = 0.5) -> dict:
    """Match one catalog item against the competitor index. Returns a match dict."""
    out = {
        "catalog_sku": item.get("sku", ""),
        "catalog_title": _rec_title(item),
        "catalog_price": item.get("price", ""),
        "method": "none", "confidence": 0.0,
    }
    sk = norm_sku(item.get("sku"))
    hit = None
    if sk and sk in index["by_sku"]:
        hit = index["by_sku"][sk][0]
        out["method"], out["confidence"] = "sku", 1.0
    else:
        sig = title_signature(_rec_title(item))
        if sig and sig in index["by_sig"]:
            hit = index["by_sig"][sig][0]
            out["method"], out["confidence"] = "title_exact", 0.9
        else:
            hit, score = _best_title_match(set(norm_tokens(_rec_title(item))),
                                           index, min_overlap)
            if hit is not None:
                out["method"], out["confidence"] = "title_fuzzy", score
                if score < 0.6:
                    out["review"] = True
    if hit is None:
        return out
    rec = index["records"][hit]
    out["match"] = {
        "origin": rec.get("origin", ""),
        "title": (rec.get("product_title", "") +
                  (f" [{rec['variant_title']}]" if rec.get("variant_title") not in ("", "Default Title") else "")),
        "sku": rec.get("sku", ""),
        "price": rec.get("price", ""),
        "available": rec.get("available", None),
        "url": rec.get("url", ""),
    }
    try:
        cp = float(item.get("price") or 0)
        mp = float(rec.get("price") or 0)
        if cp and mp:
            out["delta_pct"] = round((cp - mp) / mp * 100.0, 2)
            out["cheaper_than_competitor"] = cp < mp
    except (TypeError, ValueError):
        pass
    return out


def match_catalog(items: list, competitors: dict, min_overlap: float = 0.5) -> dict:
    """competitors: {origin: records}. Returns {origin: [match,...]}."""
    result = {}
    for origin, records in competitors.items():
        index = build_index(records)
        result[origin] = [match_item(it, index, min_overlap) for it in items]
    return result


# ---------------------------------------------------------------- reporting
def summary_lines(matches_by_origin: dict) -> list:
    lines = []
    for origin, matches in matches_by_origin.items():
        matched = [m for m in matches if m.get("match")]
        exact = [m for m in matched if m["method"] in ("sku", "title_exact")]
        review = [m for m in matched if m.get("review")]
        cheaper = [m for m in matched if m.get("cheaper_than_competitor")]
        lines.append(f"## {origin}")
        lines.append(f"- catalog items: {len(matches)} | matched: {len(matched)} | "
                     f"unmatched: {len(matches) - len(matched)}")
        lines.append(f"- strong matches (SKU / exact-title): {len(exact)}")
        lines.append(f"- flagged for review (fuzzy <0.6): {len(review)}")
        lines.append(f"- your price is lower than competitor on: {len(cheaper)} matched item(s)")
        lines.append("")
    return lines


def report_markdown(matches_by_origin: dict) -> str:
    lines = ["# Competitor price match report", ""]
    lines += summary_lines(matches_by_origin)
    for origin, matches in matches_by_origin.items():
        lines.append(f"### {origin}")
        lines.append("| Your SKU | Your title | Method | Conf | Competitor | Comp price | Your price | Change % |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for m in matches:
            mt = m.get("match")
            if not mt:
                continue
            comp = mt["title"][:48]
            lines.append(
                f"| {m['catalog_sku']} | {m['catalog_title'][:40]} | {m['method']} | "
                f"{m['confidence']} | {comp} | {mt['price']} | {m.get('catalog_price', '')} | "
                f"{m.get('delta_pct', '')} |")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI
def _load_competitors(urls) -> dict:
    comps = {}
    for u in urls:
        origin = origin_of(u)
        comps[origin] = fetch_store(origin)
    return comps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deterministic Shopify competitor price matching")
    sub = ap.add_subparsers(dest="cmd")

    m = sub.add_parser("match")
    m.add_argument("--catalog", required=True, help="storefront URL or catalog CSV path")
    m.add_argument("--competitor", action="append", default=[], required=True)
    m.add_argument("--min-overlap", type=float, default=0.5)
    m.add_argument("--out", default="price_match_report")

    f = sub.add_parser("fetch")
    f.add_argument("--store", required=True)
    f.add_argument("--out", required=True)

    r = sub.add_parser("report")
    r.add_argument("--input", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "fetch":
        recs = fetch_store(args.store)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)
        print(f"{args.store}: {len(recs)} variant records -> {args.out}")
        return 0

    if args.cmd == "match":
        try:
            items = load_catalog(args.catalog)
            comps = _load_competitors(args.competitor)
        except (ValueError, OSError, urllib.error.URLError, KeyError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        res = match_catalog(items, comps, args.min_overlap)
        md = report_markdown(res)
        with open(args.out + ".md", "w", encoding="utf-8") as fh:
            fh.write(md)
        with open(args.out + ".json", "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
        print(md)
        print(f"\nsaved {args.out}.md and {args.out}.json")
        return 0

    if args.cmd == "report":
        with open(args.input, encoding="utf-8") as fh:
            res = json.load(fh)
        print(report_markdown(res))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
