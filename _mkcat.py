import csv, json
recs = json.load(open("demo_allbirds.json", encoding="utf-8"))
seen=set(); rows=[]
for r in recs:
    sk=(r.get("sku") or "").strip()
    if not sk or sk in seen: continue
    seen.add(sk)
    rows.append({"sku":sk,"title":r["product_title"],"price":r["price"],"url":r["url"]})
    if len(rows)>=20: break
with open("demo_catalog.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.DictWriter(fh,fieldnames=["sku","title","price","url"]); w.writeheader(); w.writerows(rows)
print("catalog rows:",len(rows))
