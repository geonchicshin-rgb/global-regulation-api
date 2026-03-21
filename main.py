import os
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# 1. 깃허브 금고에서 API 키 로드
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# 2. 3.x Flash 엔진 점화 (JSON 강제화)
model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview", 
    generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
)

# 3. [웹 크롤러 가동] 구글 뉴스 글로벌 RSS (키워드: ESG regulation)
rss_url = "https://news.google.com/rss/search?q=ESG+regulation&hl=en-US&gl=US&ceid=US:en"
print("🌐 글로벌 RSS 피드 접속 중...")
response = requests.get(rss_url)
soup = BeautifulSoup(response.content, 'xml') # XML 파싱

# 가장 최신 뉴스 1개만 정밀 타겟팅하여 추출
latest_item = soup.find('item')
news_title = latest_item.title.text
news_date = latest_item.pubDate.text
news_link = latest_item.link.text

print(f"🎯 사냥 성공: [ {news_title} ]")

# AI에게 먹일 먹이(날것의 영문 데이터) 세팅
raw_text_data = f"""
Title: {news_title}
Date: {news_date}
Link: {news_link}
"""

# 4. 프롬프트 (영문을 한국어 B2B 포맷으로 번역/해석 강제)
prompt = f"""
너는 최고의 B2B 규제 분석가야. 
다음 [글로벌 영문 뉴스 데이터]를 분석해서, 한국 수출 기업들이 대응해야 할 핵심 내용을 한국어 JSON 형식으로 추출해.
반드시 아래 키 구조를 엄격하게 지킬 것.

{{
  "source_title": "뉴스 제목 (한국어 번역)",
  "original_link": "원본 뉴스 링크",
  "published_date": "발행일",
  "global_regulation_trend": "이 뉴스가 시사하는 글로벌 규제 동향 요약 (한국어)",
  "warning_for_KR_business": "한국 B2B 기업이 주의해야 할 점 또는 기회 (한국어 1문장)"
}}

[글로벌 영문 뉴스 데이터]
{raw_text_data}
"""

print("🧠 AI 분석 및 JSON 가공 중...")
response = model.generate_content(prompt)
parsed_json = json.loads(response.text)

# 5. 기존 데이터를 불러와서 새로운 데이터를 누적(Append)하여 저장
file_name = 'global_esg_live.json'
existing_data = []

# 기존 파일이 있으면 열어서 데이터를 가져옵니다.
if os.path.exists(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:
        try:
            existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []

# 만약 기존 데이터가 리스트(배열) 형태가 아니라면 리스트로 바꿉니다.
if not isinstance(existing_data, list):
    existing_data = [existing_data]

# 방금 막 번역/분석한 따끈따끈한 새 데이터를 리스트의 '맨 앞'에 추가합니다.
existing_data.insert(0, parsed_json)

# 파일 용량이 무한정 커지는 것을 막기 위해 최신 뉴스 100개까지만 유지합니다.
existing_data = existing_data[:100]

# 다시 파일로 저장합니다.
with open(file_name, 'w', encoding='utf-8') as f:
    json.dump(existing_data, f, indent=2, ensure_ascii=False)

print(f"✅ 실시간 글로벌 규제 데이터 누적 저장 완료 (현재 총 {len(existing_data)}건): {file_name}")
