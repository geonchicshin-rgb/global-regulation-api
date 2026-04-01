"""
auto_collector.py - B2A Automated Market Data Harvester
=========================================================
Adheres strictly to Core B2A Safety & Compliance Directives:
  1. ZERO SECRETS POLICY  - All API keys loaded from .env / env vars only.
  2. MANDATORY FAIL-SAFE  - Every collector is wrapped in try/except.
                            On error the system outputs a STANDBY-safe record.
  3. COMPLIANCE TERMS     - No BUY / SELL / TRADE language used.
  4. AUDIT TRACEABILITY   - Every record carries an ISO-8601 UTC timestamp.

Data sources:
  - eBay Tech deals : eBay Finding API  (EBAY_APP_ID from env)
                      Falls back to eBay public RSS if no key is set.
  - USD/KRW rate    : open.er-api.com   (free, no key required)
  - WTI crude price : Yahoo Finance API (no key required)

Output:
  market_history.jsonl  - one JSON record per line, appended every run.
"""

import os
import json
import datetime
import requests
import feedparser
from dotenv import load_dotenv
import oracle_engine
import shipping_calculator

# ── Load environment variables (ZERO SECRETS POLICY) ─────────────────────────
load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────
MARKET_HISTORY_FILE = "market_history.jsonl"
REQUEST_TIMEOUT     = 15   # seconds

# eBay Finding API endpoint (requires EBAY_APP_ID in env)
EBAY_FINDING_URL = (
    "https://svcs.ebay.com/services/search/FindingService/v1"
    "?OPERATION-NAME=findItemsByCategory"
    "&SERVICE-VERSION=1.0.0"
    "&SECURITY-APPNAME={app_id}"
    "&RESPONSE-DATA-FORMAT=JSON"
    "&categoryId=9355"          # Computers/Tablets & Networking
    "&sortOrder=BestMatch"
    "&paginationInput.entriesPerPage=5"
)
# eBay public RSS fallback (no key needed)
EBAY_RSS_URL  = "https://www.ebay.com/feeds/deals?cat=9355"
EBAY_RSS_ALT  = "https://www.ebay.com/sch/i.html?_nkw=tech+deals&_rss=1"

# Free exchange-rate API (no key required)
FX_API_URL = "https://open.er-api.com/v6/latest/USD"

# Yahoo Finance WTI crude oil futures ticker
WTI_URL = "https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF"


# ── Helper ────────────────────────────────────────────────────────────────────
def utc_now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe_get(url: str, params: dict = None, headers: dict = None) -> dict | None:
    """HTTP GET with timeout; returns parsed JSON or None on failure."""
    try:
        resp = requests.get(
            url,
            params=params,
            headers=headers or {"User-Agent": "B2A-Oracle-Collector/1.0"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"[HTTP]     GET failed for {url} - {exc}")
        return None


# ── Collector 1: eBay Tech Deals ─────────────────────────────────────────────
def fetch_ebay_tech_deals() -> dict:
    """
    Fetch the top eBay Tech/Computer deals.
    Strategy:
      1. Use eBay Finding API if EBAY_APP_ID is available.
      2. Fall back to public RSS feed (no key needed).
    Returns a dict with status and a list of deal summaries.
    """
    app_id = os.getenv("EBAY_APP_ID", "").strip()

    # --- Path A: Finding API ---
    if app_id:
        try:
            url  = EBAY_FINDING_URL.format(app_id=app_id)
            data = safe_get(url)
            if data:
                items_wrapper = (
                    data.get("findItemsByCategoryResponse", [{}])[0]
                       .get("searchResult", [{}])[0]
                       .get("item", [])
                )
                deals = []
                for item in items_wrapper[:5]:
                    title    = item.get("title", ["N/A"])[0]
                    price    = item.get("sellingStatus", [{}])[0]\
                                   .get("currentPrice", [{}])[0]\
                                   .get("__value__", "N/A")
                    currency = item.get("sellingStatus", [{}])[0]\
                                   .get("currentPrice", [{}])[0]\
                                   .get("@currencyId", "USD")
                    url_item = item.get("viewItemURL", ["N/A"])[0]
                    deals.append({
                        "title"   : title,
                        "price"   : f"{price} {currency}",
                        "url"     : url_item,
                    })
                print(f"[EBAY]     Finding API: fetched {len(deals)} deal(s).")
                return {"source": "ebay_finding_api", "category": "Computers/Tech",
                        "deals": deals, "status": "OK"}
        except Exception as exc:
            print(f"[EBAY]     Finding API error - {exc}")

    # --- Path B: Public RSS fallback ---
    for rss_url in (EBAY_RSS_URL, EBAY_RSS_ALT):
        try:
            feed = feedparser.parse(rss_url)
            if feed.entries:
                deals = []
                for entry in feed.entries[:5]:
                    deals.append({
                        "title": getattr(entry, "title", "N/A"),
                        "url"  : getattr(entry, "link",  "N/A"),
                        "price": "N/A (RSS feed)",
                    })
                print(f"[EBAY]     RSS fallback: fetched {len(deals)} deal(s) from {rss_url}")
                return {"source": "ebay_rss", "category": "Computers/Tech",
                        "deals": deals, "status": "OK"}
        except Exception as exc:
            print(f"[EBAY]     RSS error ({rss_url}) - {exc}")

    # --- Path C: All sources failed ---
    print("[EBAY]     All sources failed. Set EBAY_APP_ID in .env for reliable data.")
    return {
        "source": "none",
        "category": "Computers/Tech",
        "deals": [],
        "status": "STANDBY - no data source available",
    }


# ── Collector 2: USD/KRW Exchange Rate ───────────────────────────────────────
def fetch_usd_krw() -> dict:
    """
    Fetch the current USD -> KRW exchange rate from open.er-api.com.
    No API key required for the free tier.
    """
    try:
        data = safe_get(FX_API_URL)
        if data and data.get("result") == "success":
            krw_rate = data["rates"].get("KRW")
            if krw_rate is None:
                raise ValueError("KRW rate not found in API response.")
            print(f"[FX]       USD/KRW = {krw_rate}")
            return {
                "pair"          : "USD/KRW",
                "rate"          : round(float(krw_rate), 4),
                "base"          : "USD",
                "quote"         : "KRW",
                "provider"      : "open.er-api.com",
                "next_update_utc": data.get("time_next_update_utc", "N/A"),
                "status"        : "OK",
            }
        raise ValueError(f"Unexpected API response: {data}")
    except Exception as exc:
        print(f"[FX]       USD/KRW fetch failed - {exc}")
        return {"pair": "USD/KRW", "rate": None, "status": "STANDBY - fetch error"}


# ── Collector 3: WTI Crude Oil Price ─────────────────────────────────────────
def fetch_wti_price() -> dict:
    """
    Fetch the latest WTI crude oil futures price (CL=F) from Yahoo Finance.
    No API key required.
    """
    try:
        params = {"interval": "1d", "range": "1d"}
        headers = {
            "User-Agent"  : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept"      : "application/json",
        }
        data = safe_get(WTI_URL, params=params, headers=headers)
        if data:
            meta   = data["chart"]["result"][0]["meta"]
            price  = meta.get("regularMarketPrice")
            prev   = meta.get("chartPreviousClose")
            symbol = meta.get("symbol", "CL=F")
            currency = meta.get("currency", "USD")
            print(f"[WTI]      {symbol} = {price} {currency}")
            return {
                "ticker"        : symbol,
                "price"         : round(float(price), 4) if price else None,
                "previous_close": round(float(prev),  4) if prev  else None,
                "currency"      : currency,
                "unit"          : "USD per barrel",
                "provider"      : "Yahoo Finance",
                "status"        : "OK",
            }
        raise ValueError("Empty response from Yahoo Finance.")
    except Exception as exc:
        print(f"[WTI]      Price fetch failed - {exc}")
        return {"ticker": "CL=F", "price": None, "status": "STANDBY - fetch error"}


# ── Output: Append to market_history.jsonl ───────────────────────────────────
def append_market_record(record: dict) -> None:
    """Append one JSON record (one line) to market_history.jsonl."""
    try:
        with open(MARKET_HISTORY_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"[STORAGE]  Record appended -> {MARKET_HISTORY_FILE}")
    except Exception as exc:
        print(f"[STORAGE]  ERROR writing to {MARKET_HISTORY_FILE} - {exc}")


# ── Main orchestrator ─────────────────────────────────────────────────────────
def main() -> None:
    timestamp = utc_now_iso()
    print("=" * 60)
    print("  B2A Auto Collector - Market Data Harvest")
    print(f"  Run timestamp: {timestamp}")
    print("=" * 60)

    try:
        # 1. 데이터 수집
        ebay_data = fetch_ebay_tech_deals()
        fx_data   = fetch_usd_krw()
        wti_data  = fetch_wti_price()

        statuses = [ebay_data["status"], fx_data["status"], wti_data["status"]]
        overall  = "OK" if all(s == "OK" for s in statuses) else ("PARTIAL" if any(s == "OK" for s in statuses) else "STANDBY")

        record = {
            "timestamp"   : timestamp,
            "overall_status": overall,
            "ebay_tech"   : ebay_data,
            "usd_krw"     : fx_data,
            "wti_crude"   : wti_data,
        }
        
        # 2. 물류비 계산 (방어적 코드 적용)
        try:
            fx_rate = float(fx_data.get("rate", 1500))
            wti_price = float(wti_data.get("price", 80))
            # 테스트용 가상 상품 (향후 K-딜 수집 데이터로 교체 예정)
            test_item_usd = 50.0
            test_weight = 2.0
            
            calc_result = shipping_calculator.calculate_landed_cost(test_item_usd, test_weight, fx_rate, wti_price)
            record["calculated_shipping"] = calc_result
        except Exception as e:
            print(f"[LOGISTICS] Calculation error: {e}")
            record["calculated_shipping"] = {"status": "ERROR"}

        # 3. 오라클 AI 분석 (계산된 물류비까지 포함하여 판단)
        print("[ORACLE] 🤖 AI 분석 엔진 가동 중...")
        record["ai_analysis"] = oracle_engine.generate_insight(record)
    
    except Exception as exc:
        print(f"[FATAL]    Unhandled error - {exc}")
        record = {
            "timestamp"     : timestamp,
            "overall_status": "STANDBY",
            "error"         : str(exc),
            "ebay_tech"     : {"status": "STANDBY"},
            "usd_krw"       : {"status": "STANDBY"},
            "wti_crude"     : {"status": "STANDBY"},
            "ai_analysis"   : "STANDBY - System Error"
        }

    append_market_record(record)

    print("=" * 60)
    print(f"  Harvest complete. Status: {record['overall_status']}")
    print("=" * 60)

def run_harvest():
    # ... (환율, 유가 수집 로직) ...
    
    # 임시 상품 데이터 (이베이 API 미작동 시 테스트용)
    test_item = {"name": "K-Beauty Set", "price_usd": 50, "weight": 2}
    
    # 실시간 배송비 계산 적용
    landed_cost = shipping_calculator.get_shipping_cost(
        test_item['weight'], data['usd_krw']['rate'], data['wti_crude']['price']
    )
    
    # 오라클 분석 호출 (드디어 연결!)
    data['ai_analysis'] = oracle_engine.generate_insight(data)
    data['calculated_shipping_krw'] = landed_cost

if __name__ == "__main__":
    main()
