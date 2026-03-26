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
        
    prompt = f"""당신은 전 세계 사람들의 지갑을 열게 만드는 탑티어 제휴 마케터입니다. 
    다음 할인 뉴스 제목을 바탕으로, 사람들이 클릭하지 않고는 배길 수 없도록 가독성 높고 구체적인 세일즈 카피를 작성하세요.
    영어, 스페인어, 일본어, 한국어 4가지 언어로 작성합니다.

    [핵심 작성 규칙 - 반드시 지킬 것!]
    1. 가독성 극대화: 절대 글을 한 덩어리로 뭉쳐 쓰지 마세요. 의미가 바뀔 때마다 반드시 줄바꿈 기호(\\n)를 두 번 연속 사용해서 문단을 시원하게 나누세요.
    2. 팩트 기반 리스트(No Fake): 특정 제품이나 가격을 거짓으로 지어내지 마세요! 주어진 기사 제목을 분석해서, 사람들이 가장 기대할 만한 '핵심 할인 카테고리'나 '주목할 포인트' 3가지를 글머리 기호(✔️)로 나열하세요.
    3. 템플릿 구조:
       - [도입부] 제목을 활용한 강렬한 후킹 문장
       \\n\\n
       - [주목할 핫딜 포인트]
       ✔️ 포인트 1
       ✔️ 포인트 2
       ✔️ 포인트 3
       \\n\\n
       - [마무리] 품절 임박(FOMO) 강조 및 구매 유도 문장

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
