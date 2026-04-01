"""
auto_collector.py - B2A Automated Market Data Harvester (K-Deal Pivot)
=========================================================
Adheres strictly to Core B2A Safety & Compliance Directives.
Pivoted to Reverse-Arbitrage (KR -> Global) due to high KRW/USD exchange rates.
"""

import os
import json
import datetime
import requests
import feedparser
from dotenv import load_dotenv
import oracle_engine
import shipping_calculator

# ── Load environment variables ─────────────────────────
load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────
MARKET_HISTORY_FILE = "market_history.jsonl"
REQUEST_TIMEOUT     = 15

# [PIVOT] K-Deal (Ppomppu) RSS for Tech Deals
K_DEAL_RSS_URL = "https://www.ppomppu.co.kr/zboard/rss_feed.php?id=ppomppu"

# Free exchange-rate API
FX_API_URL = "https://open.er-api.com/v6/latest/USD"

# Yahoo Finance WTI crude oil futures ticker
WTI_URL = "https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF"

# ── Helper ────────────────────────────────────────────────────────────────────
def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def safe_get(url: str, params: dict = None, headers: dict = None) -> dict | None:
    try:
        resp = requests.get(url, params=params, headers=headers or {"User-Agent": "B2A-Oracle/1.0"}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"[HTTP]     GET failed for {url} - {exc}")
        return None

# ── Collector 1: K-Deal Tech Harvester (Replacing eBay) ──────────────────────
def fetch_korean_deals() -> dict:
    """
    Fetch the top Korean Tech deals (e.g., from Ppomppu).
    Filters for tech-related keywords to ensure relevance.
    """
    try:
        feed = feedparser.parse(K_DEAL_RSS_URL)
        deals = []
        tech_keywords = ['ssd', '램', '노트북', '아이폰', '갤럭시', '모니터', 'hdd', '충전기']
        
        for entry in feed.entries:
            title_lower = entry.title.lower()
            if any(kw in title_lower for kw in tech_keywords):
                # Extract approximate price from title if possible (simplified)
                # K-deals usually have prices in brackets like [100,000원]
                deals.append({
                    "title": entry.title,
                    "url"  : entry.link,
                    "price_krw": "Check Link" # Placeholder until NLP extraction is added
                })
            if len(deals) >= 3: # Keep top 3 to manage token limits
                break
                
        print(f"[K-DEAL]   Fetched {len(deals)} tech deal(s).")
        return {"source": "ppomppu_rss", "category": "Computers/Tech", "deals": deals, "status": "OK" if deals else "STANDBY - no deals found"}
    except Exception as exc:
        print(f"[K-DEAL]   RSS error - {exc}")
        return {"source": "none", "category": "Computers/Tech", "deals": [], "status": f"STANDBY - {exc}"}

# ── Collector 2: USD/KRW Exchange Rate ───────────────────────────────────────
def fetch_usd_krw() -> dict:
    try:
        data = safe_get(FX_API_URL)
        if data and data.get("result") == "success":
            krw_rate = data["rates"].get("KRW")
            if krw_rate is None: raise ValueError("KRW rate not found.")
            print(f"[FX]       USD/KRW = {krw_rate}")
            return {"pair": "USD/KRW", "rate": round(float(krw_rate), 4), "base": "USD", "quote": "KRW", "provider": "open.er-api.com", "status": "OK"}
        raise ValueError(f"Unexpected API response")
    except Exception as exc:
        print(f"[FX]       USD/KRW fetch failed - {exc}")
        return {"pair": "USD/KRW", "rate": None, "status": "STANDBY - fetch error"}

# ── Collector 3: WTI Crude Oil Price ─────────────────────────────────────────
def fetch_wti_price() -> dict:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        data = safe_get(WTI_URL, params={"interval": "1d", "range": "1d"}, headers=headers)
        if data:
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            print(f"[WTI]      CL=F = {price} USD")
            return {"ticker": "CL=F", "price": round(float(price), 4) if price else None, "unit": "USD per barrel", "provider": "Yahoo Finance", "status": "OK"}
        raise ValueError("Empty response.")
    except Exception as exc:
        print(f"[WTI]      Price fetch failed - {exc}")
        return {"ticker": "CL=F", "price": None, "status": "STANDBY - fetch error"}

# ── Output: Append to market_history.jsonl ───────────────────────────────────
def append_market_record(record: dict) -> None:
    try:
        with open(MARKET_HISTORY_FILE, "a", encoding="utf-8") as fh: fh.write(json.dumps(record) + "\n")
        print(f"[STORAGE]  Record appended -> {MARKET_HISTORY_FILE}")
    except Exception as exc: print(f"[STORAGE]  ERROR writing - {exc}")

# ── Main orchestrator ─────────────────────────────────────────────────────────
def main() -> None:
    timestamp = utc_now_iso()
    print("=" * 60)
    print("  B2A Auto Collector - K-Deal Reverse Arbitrage")
    print("=" * 60)

    try:
        k_deal_data = fetch_korean_deals()
        fx_data     = fetch_usd_krw()
        wti_data    = fetch_wti_price()

        statuses = [k_deal_data["status"], fx_data["status"], wti_data["status"]]
        overall  = "OK" if all("OK" in s for s in statuses) else ("PARTIAL" if any("OK" in s for s in statuses) else "STANDBY")

        record = {
            "timestamp"   : timestamp,
            "overall_status": overall,
            "k_deals"     : k_deal_data,  # Changed from ebay_tech
            "usd_krw"     : fx_data,
            "wti_crude"   : wti_data,
        }
        
        # [PIVOT] We pass the raw data to the Oracle. 
        # The AI will read the K-Deal titles and evaluate reverse-arbitrage potential.
        print("[ORACLE] 🤖 AI 분석 엔진 가동 중...")
        
        # Check if we have real data to analyze to prevent dummy hallucinations
        if not k_deal_data["deals"]:
            record["ai_analysis"] = "STANDBY - No valid deals collected. Skipping Oracle."
        else:
            record["ai_analysis"] = oracle_engine.generate_insight(record)
    
    except Exception as exc:
        print(f"[FATAL]    Unhandled error - {exc}")
        record = {
            "timestamp": timestamp, "overall_status": "STANDBY", "error": str(exc),
            "k_deals": {"status": "STANDBY"}, "usd_krw": {"status": "STANDBY"}, "wti_crude": {"status": "STANDBY"},
            "ai_analysis": "STANDBY - System Error"
        }

    append_market_record(record)
    print("=" * 60)
    print(f"  Harvest complete. Status: {record['overall_status']}")

if __name__ == "__main__":
    main()
