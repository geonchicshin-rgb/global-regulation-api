import os
import json
import time
import requests
from bs4 import BeautifulSoup
from google import genai

# 1. 깃허브 금고에서 API 키 로드
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

print("🔍 1단계: 내 API 키로 쓸 수 있는 구글 AI 모델 탐색 중...")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
response = requests.get(url).json()

# 'flash'가 포함되고 텍스트 생성을 지원하는 모델만 자동 필터링
available_models = []
if 'models' in response:
    for m in response['models']:
        if 'flash' in m.get('name', '').lower() and 'generateContent' in m.get('supportedGenerationMethods', []):
            clean_name = m['name'].replace('models/', '') # 'models/' 글자 제거
            available_models.append(clean_name)

if not available_models:
    print("❌ 앗! 사용 가능한 Flash 모델이 없습니다. API 키 상태를 확인해야 합니다.")
    best_model = "gemini-1.5-flash" # 최후의 보루
else:
    # 가장 안정적인 첫 번째 모델 자동 선택
    best_model = available_models[0]
    print(f"✅ 내 열쇠로 쓸 수 있는 모델들: {available_models}")
    print(f"🚀 자동 선택된 최적의 모델: {best_model}")

# 2. [초정밀 타겟팅] 한국 수출 3대 핵심 규제
targets = {
    "CBAM (탄소국경조정제도)": "CBAM regulation Europe",
    "CSDDD (공급망실사지침)": "CSDDD ESG supply chain",
    "EUDR (산림벌채규정)": "EUDR deforestation regulation"
}

new_results = []
print("\n🌐 2단계: 2026년형 자동 추적 다중 사냥 엔진을 가동합니다...")

for category, query in targets.items():
    print(f"🔍 탐색 중: {category}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    resp = requests.get(rss_url)
    soup = BeautifulSoup(resp.content, 'xml')
    
    latest_item = soup.find('item')
    if not latest_item:
        continue
        
    news_title = latest_item.title.text
    news_link = latest_item.link.text
    news_date = latest_item.pubDate.text
    
    # 3. 브레인 가동 (위에서 자동 선택된 best_model 사용)
    prompt = f"당신은 B2B 전문 분석가입니다. 다음 뉴스를 한국어로 요약하고 한국 수출 기업을 위한 주의사항을 JSON으로 작성하세요. 카테고리: {category}, 제목: {news_title}, 링크: {news_link}, 날짜: {news_date}"
    
    try:
        res = client.models.generate_content(
            model=best_model, 
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

final_data = new_results + existing_data
final_data = final_data[:200]

with open(file_name, 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2, ensure_ascii=False)

print(f"\n✅ 작업 종료. 현재 총 {len(final_data)}건의 데이터가 창고에 있습니다.")
