import os
import google.generativeai as genai
import json

# 1. 깃허브 금고(Secrets)에서 API 키를 몰래 꺼내옵니다.
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# 2. 3.x Flash 엔진 점화
model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview", 
    generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
)

# 3. 타겟 데이터 (추후 이 부분은 실제 크롤링 코드로 대체됩니다)
raw_text_data = """
[환경부 공지] 2026년 4월 1일부터 EU 탄소국경조정제도(CBAM)의 철강 및 알루미늄 품목 배출량 산정 기준이 대폭 강화됩니다.
기존 대비 인정 오차율이 5%에서 2.5%로 축소되며, 이를 초과할 경우 1톤당 50유로의 패널티가 부과될 예정입니다.
한국 수출 기업들은 2026년 3월 25일까지 반드시 분기별 실측 데이터를 EU 포털 시스템(CBAM Registry)에 직접 제출해야 합니다. 
기간 내 미제출 시 유럽 내 수출 통관이 즉각 보류될 수 있습니다.
"""

prompt = f"""
다음 [원문 데이터]를 분석하여 규제 정보를 추출해라. 
반드시 아래의 JSON 키 구조를 엄격하게 따를 것.
{{
  "regulation_target": "규제 대상 이름",
  "affected_industry": ["산업1", "산업2"],
  "expected_tax_penalty": "벌금/세금 상세 내용",
  "compliance_deadline": "마감일 (YYYY-MM-DD)",
  "action_required_for_KR_exporters": "한국 기업의 필수 조치사항"
}}
[원문 데이터]
{raw_text_data}
"""

print("데이터 추출 중...")
response = model.generate_content(prompt)
parsed_json = json.loads(response.text)

# 4. 추출된 데이터를 'cbam_data.json' 이라는 파일로 자동 저장합니다.
with open('cbam_data.json', 'w', encoding='utf-8') as f:
    json.dump(parsed_json, f, indent=2, ensure_ascii=False)

print("✅ 데이터 저장 완료: cbam_data.json")
