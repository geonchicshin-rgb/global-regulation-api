import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
import google.generativeai as genai

# 1. 제미나이 API 키 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

genai.configure(api_key=GEMINI_API_KEY)
client = genai

# 2. 핫딜 사냥감 리스트 (아마존, 스팀 등 할인 키워드)
targets = {
    "Tech & Gadgets": "Amazon limited time deal tech OR Best Buy sale",
    "Gaming Deals": "Steam weekend deal OR PlayStation store sale",
    "Software Tools": "AppSumo lifetime deal OR software discount"
}

def get_deal_news(query):
    try:
        encoded_query = urllib.parse.quote(query)
        # +when:1d 를 추가해서 딱 최근 24시간 이내의 따끈따끈한 할인 정보만 가져옵니다
        url = f"https://news.google.com/rss/search?q={encoded_query}+when:1d&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        items = root.findall('.//item')
        if not items:
            return None
            
        latest_deal = items[0]
        title = latest_deal.find('title').text
        link = latest_deal.find('link').text
        pub_date = latest_deal.find('pubDate').text
        return {"title": title, "link": link, "pub_date": pub_date}
    except Exception as e:
        print(f"핫딜 수집 에러 ({query}): {e}")
        return None

new_results = []

# 3. 핫딜 수집 및 AI 세일즈 카피 생성
for category, query in targets.items():
    print(f"🛒 [{category}] 글로벌 핫딜 탐색 중...")
    deal = get_deal_news(query)
    
    if not deal:
        continue
        
    prompt = f"""당신은 전 세계 사람들의 지갑을 열게 만드는 탑티어 제휴 마케터(Affiliate Marketer)입니다. 
    다음 할인 정보를 바탕으로, 사람들이 클릭하지 않고는 배길 수 없도록 가독성 높고 구체적인 세일즈 카피를 작성하세요.
    영어(English), 스페인어(Spanish), 일본어(Japanese), 한국어(Korean) 4가지 언어로 작성합니다.

    [핵심 작성 규칙 - 반드시 지킬 것!]
    1. 가독성 극대화: 절대 글을 한 덩어리로 뭉쳐 쓰지 마세요. 짧은 문장과 줄바꿈을 적극 사용하세요.
    2. 구체적인 미끼(Hook): 제목을 바탕으로, 이 세일에서 사람들이 가장 열광할 만한 '구체적인 예상 제품 3가지'를 상상하여 글머리 기호(Bullet points)로 나열하세요. (예: 💻 애플 맥북 프로 최저가, 🎧 소니 무선 헤드폰 반값 등)
    3. 구조화된 템플릿:
       - [도입부] 시선을 끄는 강렬한 후킹 문장
       - [주요 핫딜 라인업] 3가지 구체적인 아이템 리스트 (체크 표시 ✔️ 등 활용)
       - [마무리] 품절 임박을 강조하는 FOMO 자극 및 강력한 구매 유도(Call to Action)

    - 핫딜 정보: {deal['title']}
    - 날짜: {deal['pub_date']}
    """
    
    try:
        model = client.GenerativeModel("gemini-2.5-flash")
        res = model.generate_content(
            contents=prompt,
            generation_config={
                'response_mime_type': 'application/json',
                'response_schema': {
                    'type': 'object',
                    'properties': {
                        'deal_category': {'type': 'string'},
                        'original_link': {'type': 'string'},
                        'english_title': {'type': 'string'},
                        'english_sales_copy': {'type': 'string'},
                        'spanish_title': {'type': 'string'},
                        'spanish_sales_copy': {'type': 'string'},
                        'japanese_title': {'type': 'string'},
                        'japanese_sales_copy': {'type': 'string'},
                        'korean_title': {'type': 'string', 'description': 'FOMO inducing Korean title'},
                        'korean_sales_copy': {'type': 'string', 'description': 'Persuasive Korean sales copy with emojis'}
                    },
                    'required': ['deal_category', 'english_title', 'english_sales_copy', 'spanish_title', 'spanish_sales_copy', 'japanese_title', 'japanese_sales_copy', 'korean_title', 'korean_sales_copy']
                }
            }
        )
        parsed_json = json.loads(res.text)
        
        # 실제 수익화 단계에서는 이 original_link를 건식님의 '제휴 링크(Affiliate Link)'로 바꿀 것입니다.
        parsed_json['original_link'] = deal['link'] 
        parsed_json['published_date'] = datetime.utcnow().isoformat() + "Z"
        
        new_results.append(parsed_json)
        print(f"✅ [{category}] 다국어 세일즈 카피 생성 완료!")
    except Exception as e:
        print(f"❌ AI 생성 실패 ({category}): {e}")

# 4. JSON 파일로 창고에 저장
output_filename = 'global_hot_deals.json'
with open(output_filename, 'w', encoding='utf-8') as f:
    json.dump(new_results, f, ensure_ascii=False, indent=2)

print(f"🎉 핫딜 사냥 완료! {output_filename} 저장 성공.")
