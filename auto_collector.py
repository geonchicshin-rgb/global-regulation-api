"""
auto_collector.py - B2A Hybrid Market Data Harvester
=========================================================
수입(eBay)과 수출(K-Deal) 데이터를 동시에 수집하여 오라클에 전달합니다.
"""

import os, json, datetime, requests, feedparser
from dotenv import load_dotenv
import oracle_engine
import shipping_calculator

load_dotenv()

MARKET_HISTORY_FILE = "market_history.jsonl"
FX_API_URL = "https://open.er-api.com/v6/latest/USD"
WTI_URL = "https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF"
EBAY_RSS_URL = "https://www.ebay.com/sch/i.html?_nkw=tech+deals&_rss=1"
K_DEAL_RSS_URL = "https://www.ppomppu.co.kr/zboard/rss_feed.php?id=ppomppu"

def safe_get(url: str, params=None) -> dict:
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": "B2A-Bot/1.0"}, timeout=15)
        return resp.json()
    except: return {}

def fetch_rss_deals(url: str, keywords: list, source_name: str) -> list:
    """RSS 피드에서 특정 키워드가 포함된 핫딜을 최대 3개까지 추출 (토큰 절약)"""
    try:
        feed = feedparser.parse(url)
        deals = []
        for entry in feed.entries:
            if any(kw in entry.title.lower() for kw in keywords):
                deals.append({"title": entry.title, "url": entry.link})
            if len(deals) >= 3: break
        return deals
    except: return []

def main() -> None:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(f"=== B2A Auto Collector (Hybrid Mode) | {timestamp} ===")

    try:
        # 1. 쌍끌이 데이터 수집 (매크로 + 한국 + 미국)
        fx_data = safe_get(FX_API_URL).get("rates", {}).get("KRW", 1500.0)
        wti_data = safe_get(WTI_URL, params={"interval": "1d", "range": "1d"})
        wti_price = wti_data.get("chart",{}).get("result",[{}])[0].get("meta",{}).get("regularMarketPrice", 80.0)
        
        ebay_deals = fetch_rss_deals(EBAY_RSS_URL, ['laptop', 'ssd', 'apple', 'samsung'], "eBay")
        k_deals = fetch_rss_deals(K_DEAL_RSS_URL, ['ssd', '램', '노트북', '아이폰', '갤럭시'], "Ppomppu")

        record = {
            "timestamp": timestamp,
            "usd_krw": round(float(fx_data), 2),
            "wti_crude": round(float(wti_price), 2),
            "ebay_deals": ebay_deals,
            "k_deals": k_deals
        }

        # 2. 오라클 AI 분석 호출
        if not ebay_deals and not k_deals:
            record["ai_analysis"] = "STANDBY - No deals collected from either source."
        else:
            print("[ORACLE] 🤖 하이브리드 AI 분석 엔진 가동 중...")
            record["ai_analysis"] = oracle_engine.generate_insight(record)

    except Exception as exc:
        record = {"timestamp": timestamp, "overall_status": "STANDBY", "error": str(exc)}

    # 3. 데이터 저장
    with open(MARKET_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print("[STORAGE] Record appended to history.")

if __name__ == "__main__":
    main()
