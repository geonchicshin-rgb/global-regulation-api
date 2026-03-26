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
    다음 할인/세일 정보를 바탕으로, 사람들이 '지금 당장 사지 않으면 큰 손해'라고 느끼게 만드는(FOMO) 강력한 세일즈 카피를 작성하세요.
    동일한 내용을 영어(English), 스페인어(Spanish), 일본어(Japanese) 3가지 언어로 각각 번역 및 현지화하여 작성해야 합니다.
    각 언어별 콘텐츠는 이모지(Emoji)를 적극적으로 사용하고, 마지막에는 구매를 유도하는 강력한 한 문장(Call to Action)을 포함하세요.

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
                        'english_title': {'type': 'string', 'description': 'FOMO inducing English title'},
                        'english_sales_copy': {'type': 'string', 'description': 'Persuasive English sales copy with emojis'},
                        'spanish_title': {'type': 'string', 'description': 'FOMO inducing Spanish title'},
                        'spanish_sales_copy': {'type': 'string', 'description': 'Persuasive Spanish sales copy with emojis'},
                        'japanese_title': {'type': 'string', 'description': 'FOMO inducing Japanese title'},
                        'japanese_sales_copy': {'type': 'string', 'description': 'Persuasive Japanese sales copy with emojis'}
                    },
                    'required': ['deal_category', 'english_title', 'english_sales_copy', 'spanish_title', 'spanish_sales_copy', 'japanese_title', 'japanese_sales_copy']
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
