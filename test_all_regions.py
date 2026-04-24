#!/usr/bin/env python3
"""
PlayStation Store Multi-Region Research Script v2
Tests API accessibility, game counts, pricing, discounts for all PS Store regions.
Uses correct GraphQL hash from codebase.
"""

import asyncio
import json
import time
from datetime import datetime

import httpx

# All regions to test
REGIONS = [
    {"name": "🇺🇸 美国美服", "locale": "en-us", "currency": "USD", "note": "最大市场"},
    {"name": "🇯🇵 日本日服", "locale": "ja-jp", "currency": "JPY", "note": "第二大市场"},
    {"name": "🇬🇧 英国英服", "locale": "en-gb", "currency": "GBP", "note": "欧洲代表"},
    {"name": "🇩🇪 德国德服", "locale": "de-de", "currency": "EUR", "note": "欧洲大陆代表"},
    {"name": "🇫🇷 法国法服", "locale": "fr-fr", "currency": "EUR", "note": ""},
    {"name": "🇨🇦 加拿大", "locale": "en-ca", "currency": "CAD", "note": "北美双语"},
    {"name": "🇦🇺 澳大利亚", "locale": "en-au", "currency": "AUD", "note": "大洋洲"},
    {"name": "🇧🇷 巴西", "locale": "pt-br", "currency": "BRL", "note": "南美"},
    {"name": "🇲🇽 墨西哥", "locale": "es-mx", "currency": "MXN", "note": "拉美西班牙语"},
    {"name": "🇹🇼 台湾台服", "locale": "zh-hant-tw", "currency": "TWD", "note": "繁体中文"},
    {"name": "🇨🇳 中国大陆国服", "locale": "zh-cn", "currency": "CNY", "note": "如有独立store"},
    {"name": "🇰🇷 韩国韩服", "locale": "ko-kr", "currency": "KRW", "note": ""},
    {"name": "🇮🇹 意大利意服", "locale": "it-it", "currency": "EUR", "note": ""},
    {"name": "🇪🇸 西班牙西服", "locale": "es-es", "currency": "EUR", "note": ""},
    {"name": "🇳🇱 荷兰荷服", "locale": "nl-nl", "currency": "EUR", "note": ""},
    {"name": "🇵🇹 葡萄牙", "locale": "pt-pt", "currency": "EUR", "note": ""},
    {"name": "🇹🇭 泰国泰服", "locale": "th-th", "currency": "THB", "note": "东南亚"},
    {"name": "🇻🇳 越南越服", "locale": "vi-vn", "currency": "VND", "note": "东南亚"},
    {"name": "🇮🇩 印尼印尼服", "locale": "id-id", "currency": "IDR", "note": "东南亚"},
    {"name": "🇮🇳 印度印服", "locale": "en-in", "currency": "INR", "note": "南亚"},
]

# HK baseline
HK_BASELINE = {"name": "🇭🇰 香港港服(基线)", "locale": "zh-hant-hk", "currency": "HKD", "note": "已完成采集 7,048 款"}

URL = "https://web.np.playstation.com/api/graphql/v1/op"
CATEGORY_ID = "4cbf39e2-5749-4970-ba81-93a489e4570c"  # PS5 Games
# Correct hash from codebase (NOT the one from task context which was wrong)
GRAPHQL_HASH = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"


async def test_region(client, region, idx, total):
    """Test a single region's API accessibility and extract key data."""
    locale = region["locale"]
    currency = region["currency"]
    
    headers = {
        "Content-Type": "application/json",
        "x-psn-store-locale-override": locale,
        "x-apollo-operation-name": "categoryGridRetrieve",
    }
    
    body = {
        "operationName": "categoryGridRetrieve",
        "variables": {
            "id": CATEGORY_ID,
            "pageArgs": {"offset": 0, "size": 24},
            "currency": currency,
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": GRAPHQL_HASH
            }
        }
    }
    
    result = {
        "region_name": region["name"],
        "locale": locale,
        "currency": currency,
        "note": region["note"],
        "accessible": False,
        "status_code": None,
        "error": None,
        "total_games": None,
        "products_count": 0,
        "has_pricing": False,
        "has_discounts": False,
        "discounted_count": 0,
        "sample_game_names": [],
        "sample_prices": [],
        "response_time_ms": None,
        "product_structure_keys": [],
    }
    
    try:
        start = time.monotonic()
        resp = await client.post(URL, json=body, headers=headers)
        elapsed = (time.monotonic() - start) * 1000
        result["response_time_ms"] = round(elapsed, 1)
        result["status_code"] = resp.status_code
        
        if resp.status_code != 200:
            # Get full error body for debugging
            err_body = resp.text[:500]
            result["error"] = f"HTTP {resp.status_code}: {err_body}"
            return result
        
        data = resp.json()
        
        # Navigate to products
        try:
            grid = data.get("data", {}).get("categoryGridRetrieve", {})
            
            if not grid:
                result["error"] = f"No categoryGridRetrieve. Keys in data: {list(data.get('data', {}).keys())}"
                errors = data.get("errors", [])
                if errors:
                    result["error"] = f"GraphQL errors: {json.dumps(errors[:2], ensure_ascii=False)}"
                return result
            
            page_info = grid.get("pageInfo", {})
            result["total_games"] = page_info.get("totalCount")
            
            products = grid.get("products", [])
            result["products_count"] = len(products)
            
            discounted = 0
            has_pricing_any = False
            
            for p in products[:12]:
                name = p.get("name", "")
                result["sample_game_names"].append(name)
                
                # Check product structure keys on first item
                if len(result["product_structure_keys"]) == 0:
                    result["product_structure_keys"] = list(p.keys())
                
                # Try to find price data - check all possible locations
                price_data = None
                
                # Direct price fields at top level
                for price_key in ["price", "defaultPrice", "displayPrice"]:
                    if price_key in p:
                        price_data = p[price_key]
                        break
                
                # Nested price in common containers
                if price_data is None:
                    for container in ["skus", "offers", "multiCurrencyPrices"]:
                        if container in p:
                            container_val = p[container]
                            items = container_val if isinstance(container_val, list) else [container_val]
                            for item in items:
                                if isinstance(item, dict):
                                    for pk in ["price", "actualPrice", "displayPrice"]:
                                        if pk in item:
                                            price_data = item[pk]
                                            break
                                if price_data:
                                    break
                        if price_data:
                            break
                
                if price_data and isinstance(price_data, dict):
                    has_pricing_any = True
                    
                    base_price = (
                        price_data.get("basePrice") or 
                        price_data.get("base_price") or 
                        price_data.get("value") or 
                        price_data.get("amount")
                    )
                    discounted_price = (
                        price_data.get("discountedPrice") or 
                        price_data.get("discounted_price") or 
                        price_data.get("discountValue")
                    )
                    discount_text = (
                        price_data.get("discountText") or 
                        price_data.get("discount_text") or 
                        price_data.get("discountPercentage")
                    )
                    
                    price_info = {
                        "game": name[:50],
                        "base": base_price,
                        "discounted": discounted_price,
                        "discount_text": discount_text,
                        "all_keys": list(price_data.keys()),
                    }
                    result["sample_prices"].append(price_info)
                    
                    if discounted_price or discount_text:
                        discounted += 1
                
                # Top-level discount flags
                if p.get("isDiscounted") or p.get("hasDiscount"):
                    if discounted == 0 or name not in [sp.get("game", "") for sp in result["sample_prices"][-3:]]:
                        discounted += 1
            
            result["has_pricing"] = has_pricing_any
            result["has_discounts"] = discounted > 0
            result["discounted_count"] = discounted
            result["accessible"] = True
            
        except Exception as e:
            result["error"] = f"Parsing error: {str(e)}"
            result["raw_sample"] = json.dumps(data, ensure_ascii=False)[:800]
    
    except httpx.TimeoutException:
        result["error"] = "Timeout (30s)"
    except httpx.HTTPError as e:
        result["error"] = f"HTTP Error: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected: {type(e).__name__}: {str(e)}"
    
    return result


async def main():
    print("=" * 110)
    print("PlayStation Store 多区域数据抓取调研 v2 (使用正确GraphQL Hash)")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"待测区域数: {len(REGIONS)} + 1 基线(HK)")
    print(f"GraphQL Hash: {GRAPHQL_HASH[:20]}...")
    print("=" * 110)
    print()
    
    all_regions = [HK_BASELINE] + REGIONS
    results = []
    
    async with httpx.AsyncClient(timeout=30) as client:
        for i, region in enumerate(all_regions):
            flag_emoji = region["name"].split()[0]
            print(f"[{i+1:>2}/{len(all_regions)}] 测试 {region['name']:<22} ({region['locale']}/{region['currency']})...", end=" ", flush=True)
            
            result = await test_region(client, region, i, len(all_regions))
            results.append(result)
            
            if result["accessible"]:
                total = result["total_games"]
                status = f"✅ 可达 | 总数:{total:,} | 折扣:{result['discounted_count']}款 | {result['response_time_ms']}ms"
            else:
                err_short = (result.get('error') or '')[:55]
                status = f"❌ 失败 | {err_short}"
            
            print(status)
            
            # Rate limiting
            await asyncio.sleep(0.5)
    
    # ===== SUMMARY TABLE =====
    print()
    print("=" * 115)
    print("调研结果总览表")
    print("=" * 115)
    
    print(f"\n{'区域':<24} {'Locale':<14} {'货币':<6} {'状态':<6} {'游戏总数':>9} {'折扣':>5} {'耗时(ms)':>8}  备注")
    print("-" * 115)
    
    for r in results:
        name = r["region_name"][:22]
        locale = r["locale"]
        currency = r["currency"]
        status = "✅可达" if r["accessible"] else "❌失败"
        total = f"{r['total_games']:,}" if r["total_games"] else "N/A"
        disc = str(r["discounted_count"]) if r["accessible"] else "-"
        rt = str(r["response_time_ms"]) if r["response_time_ms"] else "-"
        note = r["note"][:18] if r["note"] else ""
        
        print(f"{name:<24} {locale:<14} {currency:<6} {status:<6} {total:>9} {disc:>5} {rt:>8}  {note}")
    
    # ===== DETAILED ANALYSIS FOR ACCESSIBLE REGIONS =====
    accessible_results = [r for r in results if r["accessible"]]
    
    if accessible_results:
        print("\n" + "=" * 115)
        print("详细分析 — 可达区域")
        print("=" * 115)
        
        for r in accessible_results:
            print(f"\n{'─'*80}")
            print(f"📍 {r['region_name']} ({r['locale']} / {r['currency']})")
            print(f"   游戏总数:     {r['total_games']:,}")
            print(f"   首页产品数:   {r['products_count']}")
            print(f"   有价格数据:   {'✅ 是' if r['has_pricing'] else '❌ 否'}")
            print(f"   首页折扣游戏: {r['discounted_count']} 款")
            print(f"   响应时间:     {r['response_time_ms']} ms")
            
            if r["sample_game_names"]:
                print(f"   示例游戏名称:")
                for j, name in enumerate(r["sample_game_names"][:6]):
                    print(f"      {j+1}. {name}")
            
            if r["sample_prices"]:
                print(f"   价格数据示例:")
                for sp in r["sample_prices"][:4]:
                    print(f"      • {sp['game']}")
                    print(f"        base={sp['base']} | discounted={sp['discounted']} | discount={sp['discount_text']}")
                    print(f"        价格对象字段: {sp['all_keys']}")
            
            if r["product_structure_keys"]:
                print(f"   Product对象顶层字段 ({len(r['product_structure_keys'])}个):")
                keys_str = ", ".join(r["product_structure_keys"])
                print(f"      {keys_str}")
    
    # ===== COMPARISON WITH HK =====
    print("\n" + "=" * 115)
    print("与港服对比分析")
    print("=" * 115)
    
    hk_result = results[0]
    hk_total = hk_result.get("total_games") or 7048
    
    print(f"\n  🇭🇰 港服基线: {hk_total:,} 款游戏 (已完成全量采集)")
    print(f"\n  {'区域':<24} {'游戏总数':>9} {'vs HK差值':>10} {'差异%':>8}")
    print(f"  {'-'*58}")
    
    for r in accessible_results[1:]:
        if r["total_games"]:
            diff = r["total_games"] - hk_total
            pct = (diff / hk_total * 100) if hk_total else 0
            sign = "+" if diff >= 0 else ""
            print(f"  {r['region_name'][:22]:<24} {r['total_games']:>9,} {sign}{diff:>10} {pct:>+7.1f}%")
    
    # ===== FAILED REGIONS DETAIL =====
    failed_results = [r for r in results if not r["accessible"]]
    if failed_results:
        print("\n" + "=" * 115)
        print("失败区域详情")
        print("=" * 115)
        
        for r in failed_results:
            print(f"\n  ❌ {r['region_name']} ({r['locale']}/{r['currency']})")
            print(f"      HTTP Status: {r['status_code']}")
            print(f"      Error: {r.get('error', 'N/A')[:120]}")
    
    # ===== SAVE RESULTS =====
    output_file = "/home/agentuser/ps5-hk-scraper/docs/multi_region_research_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "graphql_hash_used": GRAPHQL_HASH,
            "total_regions_tested": len(all_regions),
            "accessible_count": len(accessible_results),
            "failed_count": len(failed_results),
            "hk_baseline": hk_total,
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n\n✅ 完整结果已保存至: {output_file}")
    print(f"   可达区域: {len(accessible_results)}/{len(all_regions)}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
