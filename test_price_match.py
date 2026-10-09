# -*- coding: utf-8 -*-
"""Offline tests for price_match (no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import price_match as pm  # noqa: E402


def rec(sku, title, price, variant="", origin="https://comp.example"):
    return {"origin": origin, "product_title": title, "variant_title": variant,
            "sku": sku, "price": price, "available": True,
            "url": origin + "/products/" + title.lower().replace(" ", "-")}


COMPETITOR = [
    rec("ABC-123", "Blue Widget", "19.99", "Small"),
    rec("ABC-124", "Blue Widget", "24.99", "Large"),
    rec("", "Red Gadget Pro", "39.00"),
    rec("XY 900", "Steel Bracket 10mm", "5.50"),
]


def test_norm_sku():
    assert pm.norm_sku("abc-123") == "ABC123"
    assert pm.norm_sku("XY 900") == "XY900"
    assert pm.norm_sku(None) == ""
    assert pm.norm_sku("  a.b/c ") == "ABC"


def test_title_signature_order_independent():
    a = pm.title_signature("Blue Widget Small")
    b = pm.title_signature("small blue widget")
    assert a == b
    # stopwords dropped
    assert "the" not in pm.title_signature("The Blue Widget")


def test_exact_sku_match():
    idx = pm.build_index(COMPETITOR)
    out = pm.match_item({"sku": "abc-123", "title": "Whatever", "price": "22.00"}, idx)
    assert out["method"] == "sku"
    assert out["confidence"] == 1.0
    assert out["match"]["price"] == "19.99"
    # 22.00 vs 19.99 -> we are more expensive by ~10%
    assert out["cheaper_than_competitor"] is False
    assert abs(out["delta_pct"] - 10.06) < 0.05


def test_exact_title_scores_below_sku():
    idx = pm.build_index(COMPETITOR)
    out = pm.match_item({"sku": "ZZZ", "title": "Red Gadget Pro", "price": "35"}, idx)
    assert out["method"] == "title_exact"
    assert out["confidence"] == 0.9
    assert out["match"]["price"] == "39.00"
    assert out["cheaper_than_competitor"] is True


def test_fuzzy_title_and_review_flag():
    idx = pm.build_index(COMPETITOR)
    # "Steel Bracket" shares significant tokens with "Steel Bracket 10mm"
    out = pm.match_item({"sku": "", "title": "Steel Bracket", "price": "5.00"}, idx)
    assert out["method"] == "title_fuzzy"
    assert out["confidence"] >= 0.5
    assert out["match"]["sku"] == "XY 900"


def test_no_match():
    idx = pm.build_index(COMPETITOR)
    out = pm.match_item({"sku": "NOPE", "title": "Completely Unrelated Product Zzz",
                         "price": "1.00"}, idx)
    assert out["method"] == "none"
    assert "match" not in out


def test_match_catalog_and_report():
    comps = {"https://comp.example": COMPETITOR}
    items = [
        {"sku": "ABC-123", "title": "Blue Widget", "price": "22.00"},
        {"sku": "", "title": "Red Gadget Pro", "price": "35.00"},
    ]
    res = pm.match_catalog(items, comps)
    assert "https://comp.example" in res
    assert len(res["https://comp.example"]) == 2
    md = pm.report_markdown(res)
    assert "Competitor price match report" in md
    assert "ABC-123" in md


def test_origin_of():
    assert pm.origin_of("example.com") == "https://example.com"
    assert pm.origin_of("https://shop.example.com/x") == "https://shop.example.com"
