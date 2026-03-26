import os
import json
import time
import requests
from bs4 import BeautifulSoup
from google import genai  # 최신 SDK 사용

# 1. 깃허브 금고에서 API 키 로드
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# 2. [초정밀 타겟팅] 한국 수출 3대 핵심 규제
targets = {
    "CBAM (탄소국경조정제도)": "CBAM regulation Europe",
    "CSDDD (공급망실사지침)": "CSDDD ESG supply chain",
    "EUDR (산림벌채규정)": "EUDR deforestation regulation"
}

new_results = []

print("🌐 2026년형 다중 사냥 엔진을 가동합니다...")

for category, query in targets.items():
    print(f"🔍 탐색 중: {category}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(rss_url)
    soup = BeautifulSoup(response.content, 'xml')
    
    latest_item = soup.find('item')
    if not latest_item:
        continue
        
    news_title = latest_item.title.text
    news_link = latest_item.link.text
    news_date = latest_item.pubDate.text
    
    # 3. 신형 엔진(gemini-2.0-flash) 호출 (가장 안정적인 최신 표준)
    prompt = f"당신은 B2B 전문 분석가입니다. 다음 뉴스를 한국어로 요약하고 한국 수출 기업을 위한 주의사항을 JSON으로 작성하세요. 카테고리: {category}, 제목: {news_title}, 링크: {news_link}"
    
    try:
        # 최신 SDK의 호출 방식입니다.
        res = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': {
                    'type': 'object',
                    'properties': {
                        'regulation_category': {'type': 'string'},
                        'source_title': {'type': 'string'},
                        'original_link': {'type': 'string'},
                        'published_date': {'type': 'string'},
                        'global_regulation_trend': {'type': 'string'},
                        'warning_for_KR_business': {'type': 'string'},
                    }
                }
            }
        )
        parsed_json = json.loads(res.text)
        new_results.append(parsed_json)
        print(f"🎯 {category} 분석 완료!")
    except Exception as e:
        print(f"❌ {category} 분석 실패: {e}")
        
    time.sleep(2)

# 4. 데이터 저장 로직 (누적형)
file_name = 'global_esg_live.json'
existing_data = []

if os.path.exists(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:
        try:
            existing_data = json.load(f)
        except:
            existing_data = []

# 새 데이터 3개를 맨 앞으로!
final_data = new_results + existing_data
final_data = final_data[:200]

with open(file_name, 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2, ensure_ascii=False)

print(f"✅ 작업 종료. 현재 총 {len(final_data)}건의 데이터가 창고에 있습니다.")
