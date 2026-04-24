#!/usr/bin/env python3
import asyncio, json, time
from datetime import datetime
import httpx

URL = "https://web.np.playstation.com/api/graphql/v1/op"
CAT_ID = "4cbf39e2-5749-4970-ba81-93a489e4570c"
HASH = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"

async def fetch(client, loc, cur, off=0, sz=24):
    h = {"Content-Type": "application/json", "x-psn-store-locale-override": loc, "x-apollo-operation-name": "categoryGridRetrieve"}
    b = {"operationName": "categoryGridRetrieve", "variables": {"id": CAT_ID, "pageArgs": {"offset": off, "size": sz}, "currency": cur}, "extensions": {"persistedQuery": {"version": 1, "sha256Hash": HASH}}}
    r = await client.post(URL, json=b, headers=h)
    return r.json()

async def find_disc(client, loc, cur, name, pages=5):
    print("")
    print("=" * 60)
    print("Discount search: {} ({}/{})".format(name, loc, cur))
    print("=" * 60)
    disc = []
    for p in range(pages):
        try:
            d = await fetch(client, loc, cur, offset=p*24)
            g = d.get("data",{}).get("categoryGridRetrieve",{})
            prods = g.get("products",[])
            if not prods:
                break
            for prod in prods:
                pr = prod.get("price",{})
                dt = pr.get("discountText","")
                if dt and dt.strip():
                    disc.append({"name":prod["name"],"base":pr.get("basePrice"),"disc":pr.get("discountedPrice"),"text":dt})
            t = g.get("pageInfo",{}).get("totalCount","?")
            dc = len([x for x in prods if x.get("price",{}).get("discountText","")])
            print("  Page {}: {} discounted | total: {}".format(p+1, dc, t))
            if len(disc) >= 10:
                break
        except Exception as e:
            print("  Err page {}: {}".format(p+1, e))
            break
        await asyncio.sleep(0.3)
    if disc:
        print("  Found {} discounted:".format(len(disc)))
        for x in disc[:10]:
            nm = x["name"][:55]
            print("    * {}".format(nm))
            bp = x["base"]; dp = x["disc"]; dt2 = x["text"]
            print("      {} -> {} ({})".format(bp, dp, dt2))
    else:
        print("  No discounts found")
    return disc

async def inv(client, loc, cur, name):
    print("")
    print("=" * 60)
    print("Investigate: {} ({}/{})".format(name, loc, cur))
    print("=" * 60)
    try:
        d = await fetch(client, loc, cur)
        print("  Top keys: {}".format(list(d.keys())))
        if "data" in d:
            dd = d["data"]
            print("  data keys: {}".format(list(dd.keys())))
            if "categoryGridRetrieve" in dd:
                g = dd["categoryGridRetrieve"]
                if isinstance(g, dict):
                    print("  grid keys: {}".format(list(g.keys())))
                    pi = g.get("pageInfo",{})
                    print("  pageInfo: {}".format(pi))
                    ps = g.get("products",[])
                    print("  products: {}".format(len(ps)))
                    if ps:
                        print("  First: {}".format(json.dumps(ps[0], ensure_ascii=False)[:500]))
                    else:
                        print("  NO PRODUCTS!")
            else:
                print("  No grid. data={}".format(json.dumps(dd, ensure_ascii=False)[:400]))
        if "errors" in d:
            print("  ERRORS: {}".format(json.dumps(d["errors"], ensure_ascii=False)[:400]))
    except Exception as e:
        print("  Error: {}".format(e))
