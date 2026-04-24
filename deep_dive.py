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
    print(f"
{'='*60}")
    print(f"Discount search: {name} ({loc}/{cur})")
    print(f"{'='*60}")
    disc = []
    for p in range(pages):
        try:
            d = await fetch(client, loc, cur, offset=p*24)
            g = d.get("data",{}).get("categoryGridRetrieve",{})
            prods = g.get("products",[])
            if not prods: break
            for prod in prods:
                pr = prod.get("price",{})
                dt = pr.get("discountText","")
                if dt and dt.strip():
                    disc.append({"name":prod["name"],"base":pr.get("basePrice"),"disc":pr.get("discountedPrice"),"text":dt})
            t = g.get("pageInfo",{}).get("totalCount","?")
            dc = len([x for x in prods if x.get("price",{}).get("discountText","")])
            print(f"  Page {p+1}: {dc} discounted | total: {t}")
            if len(disc) >= 10: break
        except Exception as e:
            print(f"  Err page {p+1}: {e}"); break
        await asyncio.sleep(0.3)
    if disc:
        print(f"  Found {len(disc)} discounted:")
        for x in disc[:10]:
            print(f"    * {x['name'][:55]}")
            print(f"      {x['base']} -> {x['disc']} ({x['text']})")
    else:
        print(f"  No discounts found")
    return disc

async def inv(client, loc, cur, name):
    print(f"
{'='*60}")
    print(f"Investigate: {name} ({loc}/{cur})")
    print(f"{'='*60}")
    try:
        d = await fetch(client, loc, cur)
        print(f"  Top keys: {list(d.keys())}")
        if "data" in d:
            dd = d["data"]
            print(f"  data keys: {list(dd.keys())}")
            if "categoryGridRetrieve" in dd:
                g = dd["categoryGridRetrieve"]
                if isinstance(g, dict):
                    print(f"  grid keys: {list(g.keys())}")
                    print(f"  pageInfo: {g.get('pageInfo',{})}")
                    ps = g.get('products',[])
                    print(f"  products: {len(ps)}")
                    if ps:
                        print(f"  First: {json.dumps(ps[0], ensure_ascii=False)[:500]}")
                    else:
                        print(f"  NO PRODUCTS!")
            else:
                print(f"  No grid. data={json.dumps(dd, ensure_ascii=False)[:400]}")
        if "errors" in d:
            print(f"  ERRORS: {json.dumps(d['errors'], ensure_ascii=False)[:400]}")
    except Exception as e:
        print(f"  Error: {e}")

async def main():
    print("="*60)
    print("DEEP DIVE: Discounts + Special Regions + Cross-region IDs")
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("="*60)
    async with httpx.AsyncClient(timeout=30) as c:
        await find_disc(c, "en-us", "USD", "US", 10)
        await find_disc(c, "zh-hant-hk", "HKD", "HK", 10)
        await find_disc(c, "ja-jp", "JPY", "JP", 5)
        await inv(c, "th-th", "THB", "TH(0games)")
        await inv(c, "id-id", "IDR", "ID(0games)")
        await inv(c, "vi-vn", "VND", "VN(error)")
        await inv(c, "zh-cn", "CNY", "CN(35games)")
        
        print(f"
{'='*60}")
        print("Cross-region ID comparison (npTitleId)")
        print("="*60)
        regs = [("HK","zh-hant-hk","HKD"),("US","en-us","USD"),("JP","ja-jp","JPY"),("TW","zh-hant-tw","TWD"),("KR","ko-kr","KRW")]
        aids = {}
        for rn,rl,rc in regs:
            try:
                d = await fetch(c, rl, rc)
                ps = d.get("data",{}).get("categoryGridRetrieve",{}).get("products",[])
                ids = [p.get("npTitleId","") for p in ps]
                aids[rn] = ids
                print(f"  {rn}: {len(ids)} IDs -> {ids[:8]}...")
            except Exception as e:
                print(f"  {rn}: ERR {e}")
            await asyncio.sleep(0.3)
        if len(aids) >= 2:
            ref = list(aids.keys())[0]
            rids = set(aids[ref])
            print(f"
  vs {ref} overlap:")
            for nm,ids in aids.items():
                if nm==ref: continue
                s=set(ids); o=len(rids&s); or_=len(rids-s); ot=len(s-rids)
                print(f"    {nm}: overlap{o} | only{ref}{or_} | only{nm}{ot}")

asyncio.run(main())
