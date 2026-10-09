#!/usr/bin/env python3
"""Regenerate the repo's sample report (demo_report.json/.md + demo_catalog.csv).

Runs the actual price_match code against a small explicit competitor catalog so
the published demo shows real tool behaviour: exact SKU matches with price
deltas in both directions, a high-confidence fuzzy match, a low-confidence
fuzzy match flagged for review, and an unmatched row.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import price_match as pm  # noqa: E402

ORIGIN = "https://acme-outdoor.example"

COMPETITOR = [
    {"origin": ORIGIN, "product_title": "Trail Runner Shoes", "variant_title": "Men's 10",
     "sku": "TRK-1001", "price": "89.99", "available": True,
     "url": ORIGIN + "/products/trail-runner-shoes?variant=1"},
    {"origin": ORIGIN, "product_title": "Trail Runner Shoes", "variant_title": "Men's 11",
     "sku": "TRK-1002", "price": "89.99", "available": True,
     "url": ORIGIN + "/products/trail-runner-shoes?variant=2"},
    {"origin": ORIGIN, "product_title": "Hydration Pack 2L", "variant_title": "Default Title",
     "sku": "HYD-2040", "price": "39.50", "available": True,
     "url": ORIGIN + "/products/hydration-pack-2l"},
    {"origin": ORIGIN, "product_title": "Sleeping Bag Envelope", "variant_title": "Default Title",
     "sku": "EGD-100", "price": "59.00", "available": False,
     "url": ORIGIN + "/products/sleeping-bag-envelope"},
    {"origin": ORIGIN, "product_title": "Utility Cord 30m", "variant_title": "Default Title",
     "sku": "RO-300", "price": "7.25", "available": True,
     "url": ORIGIN + "/products/utility-cord-30m"},
]

CATALOG = [
    {"sku": "TRK-1001", "title": "Trail Runner Shoes - Men's 10", "price": "99.00"},
    {"sku": "TRK-1002", "title": "Trail Runner Shoes - Men's 11", "price": "89.99"},
    {"sku": "HYD-2040", "title": "Hydration Pack 2L", "price": "34.95"},
    {"sku": "", "title": "Sleeping Bag Envelope Plus", "price": "64.99"},
    {"sku": "", "title": "Trail Sandal - Womens 7", "price": "45.00"},
    {"sku": "ST-900", "title": "Steel Tent Stake (4 pack)", "price": "11.00"},
]

comp_idx = pm.build_index(COMPETITOR)
results = {ORIGIN: [pm.match_item(i, comp_idx) for i in CATALOG]}

print(json.dumps(results, ensure_ascii=False, indent=1))

md = pm.report_markdown(results)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_report.json"),
     "w", encoding="utf-8").write(json.dumps(results, ensure_ascii=False, indent=1))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_report.md"),
     "w", encoding="utf-8").write(md)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_catalog.csv"),
          "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["sku", "title", "price", "url"])
    for i in CATALOG:
        w.writerow([i["sku"], i["title"], i["price"],
                    "https://your-store.example/products/" +
                    i["title"].lower().replace(" - ", "-").replace(" ", "-")])
print("wrote demo_report.json, demo_report.md, demo_catalog.csv")