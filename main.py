import os
import json
import time
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# 1. 깃허브 금고에서 API 키 로드
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# 2. 최신 3세대 Flash 엔진 점화 (안정성과 지능 동시 확보, JSON 강제화)
model = genai.GenerativeModel(
    model_name="gemini-3-flash", 
    generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
)

# 3. [초정밀 타겟팅] 한국 수출 3대 핵심 규제 키워드 세팅
targets = {
    "CBAM (탄소국경조정제도)": "CBAM regulation Europe",
    "CSDDD (공급망실사지침)": "CSDDD ESG supply chain",
    "EUDR (산림벌채규정)": "EUDR deforestation regulation"
}

new_results = []

# 4. 3가지 규제 키워드를 돌면서 각각 최고급 뉴스 사냥
print("🌐 글로벌 3대 규제 다중 사냥을 시작합니다...")

for category, query in targets.items():
    print(f"🔍 탐색 중: {category}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(rss_url)
    soup = BeautifulSoup(response.content, 'xml')
    
    latest_item = soup.find('item')
    if not latest_item:
        continue
        
    news_title = latest_item.title.text
    news_date = latest_item.pubDate.text
    news_link = latest_item.link.text
    
    raw_text_data = f"Title: {news_title}\nDate: {news_date}\nLink: {news_link}"
    
    # 5. 프롬프트 (카테고리 분류 항목 추가)
    prompt = f"""
    너는 최고의 B2B 규제 분석가야. 
    다음 [글로벌 영문 뉴스 데이터]를 분석해서, 한국 수출 기업들이 대응해야 할 핵심 내용을 한국어 JSON 형식으로 추출해.
    반드시 아래 키 구조를 엄격하게 지킬 것.
    
    {{
      "regulation_category": "{category}",
      "source_title": "뉴스 제목 (한국어 번역)",
      "original_link": "원본 뉴스 링크",
      "published_date": "발행일",
      "global_regulation_trend": "이 뉴스가 시사하는 글로벌 규제 동향 요약 (한국어)",
      "warning_for_KR_business": "한국 B2B 기업이 주의해야 할 점 또는 기회 (한국어 1문장)"
    }}
    
    [글로벌 영문 뉴스 데이터]
    {raw_text_data}
    """
    
    try:
        res = model.generate_content(prompt)
        parsed_json = json.loads(res.text)
        new_results.append(parsed_json)
        print(f"🎯 사냥 성공 및 AI 분석 완료: {category}")
    except Exception as e:
        print(f"❌ 에러 발생 ({category}): {e}")
        
    # AI API 과부하를 막기 위해 2초 휴식
    time.sleep(2)

# 6. 기존 데이터에 3개의 새 데이터를 누적(Prepend)하여 저장
file_name = 'global_esg_live.json'
existing_data = []

if os.path.exists(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:
        try:
            existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []

if not isinstance(existing_data, list):
    existing_data = [existing_data]

# 방금 분석한 3개의 규제 데이터를 기존 리스트의 맨 앞에 병합합니다.
existing_data = new_results + existing_data

# 데이터가 깊어지므로 최대 보관 개수를 200개로 늘립니다.
existing_data = existing_data[:200]

with open(file_name, 'w', encoding='utf-8') as f:
    json.dump(existing_data, f, indent=2, ensure_ascii=False)

print(f"✅ 3대 규제 딥다이브 데이터 누적 완료! (현재 총 {len(existing_data)}건)")
