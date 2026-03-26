import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
import google.generativeai as genai

# 1. 제미나이 API 키 설정 (깃허브 Secrets에서 가져옴)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

genai.configure(api_key=GEMINI_API_KEY)
client = genai

# 2. 글로벌 테크/AI 사냥감 리스트
targets = {
    "AI Revolution": "OpenAI ChatGPT breakthrough OR Google Gemini update",
    "Apple News": "Apple iPhone leak OR Apple Vision Pro",
    "Global Tech Trends": "Nvidia GPU tech OR Elon Musk Tesla news"
}

def get_google_news(query):
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        items = root.findall('.//item')
        if not items:
            return None
            
        latest_news = items[0]
        title = latest_news.find('title').text
        link = latest_news.find('link').text
        pub_date = latest_news.find('pubDate').text
        return {"title": title, "link": link, "pub_date": pub_date}
    except Exception as e:
        print(f"뉴스 수집 에러 ({query}): {e}")
        return None

new_results = []

# 3. 뉴스 수집 및 AI 다국어 블로그 생성
for category, query in targets.items():
    print(f"🔍 [{category}] 글로벌 뉴스 수집 중...")
    news = get_google_news(query)
    
    if not news:
        continue
        
    prompt = f"""당신은 전 세계 수백만 명의 방문자를 이끄는 글로벌 탑티어 테크 블로거입니다. 
    다음 기사를 바탕으로, 검색엔진(SEO) 상위에 노출될 수 있는 자극적이고 흥미로운 블로그 포스팅을 작성하세요.
    동일한 내용을 영어(English), 스페인어(Spanish), 일본어(Japanese) 3가지 언어로 각각 번역 및 현지화하여 작성해야 합니다.
    각 언어별 콘텐츠는 이모지(Emoji)를 적절히 섞어 3~4문단으로 작성하세요.

    - 기사 제목: {news['title']}
    - 기사 날짜: {news['pub_date']}
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
                        'topic_category': {'type': 'string'},
                        'original_link': {'type': 'string'},
                        'english_title': {'type': 'string', 'description': 'Clickbait style English title'},
                        'english_content': {'type': 'string', 'description': 'SEO optimized English content with emojis'},
                        'spanish_title': {'type': 'string', 'description': 'Clickbait style Spanish title'},
                        'spanish_content': {'type': 'string', 'description': 'SEO optimized Spanish content with emojis'},
                        'japanese_title': {'type': 'string', 'description': 'Clickbait style Japanese title'},
                        'japanese_content': {'type': 'string', 'description': 'SEO optimized Japanese content with emojis'}
                    },
                    'required': ['topic_category', 'english_title', 'english_content', 'spanish_title', 'spanish_content', 'japanese_title', 'japanese_content']
                }
            }
        )
        parsed_json = json.loads(res.text)
        parsed_json['original_link'] = news['link']
        parsed_json['published_date'] = datetime.utcnow().isoformat() + "Z"
        
        new_results.append(parsed_json)
        print(f"✅ [{category}] 다국어 블로그 포스팅 생성 완료!")
    except Exception as e:
        print(f"❌ AI 생성 실패 ({category}): {e}")

# 4. JSON 파일로 창고에 저장 (1공장 데이터와 겹치지 않게!)
output_filename = 'global_tech_blog.json'
with open(output_filename, 'w', encoding='utf-8') as f:
    json.dump(new_results, f, ensure_ascii=False, indent=2)

print(f"🎉 모든 작업 완료! {output_filename} 저장 성공.")
