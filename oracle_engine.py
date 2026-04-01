import os, json, base64, datetime, feedparser
from dotenv import load_dotenv
from google import genai
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

# --- Constants ---
CONFIDENCE_THRESHOLD = 90
AUDIT_LOG_FILE = "audit_history.jsonl"

def generate_rsa_signature(payload_str: str):
    # [PIVOT 1] 지휘관님의 영구 인감을 우선적으로 찾습니다.
    private_key_str = os.getenv("RSA_PRIVATE_KEY", "")
    
    if private_key_str:
        private_key = serialization.load_pem_private_key(private_key_str.encode(), password=None)
    else:
        # 로컬 테스트용 임시 도장
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
    signature = private_key.sign(payload_str.encode(), padding.PKCS1v15(), hashes.SHA256())
    pub_pem = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return base64.b64encode(signature).decode(), pub_pem

def generate_insight(record: dict) -> str:
    """auto_collector가 호출하는 핵심 입구(Entry Point)"""
    load_dotenv()
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    # 1. 뉴스 및 시장 데이터 결합
    news = feedparser.parse("https://finance.yahoo.com/news/rssindex").entries[:2]
    headlines = [n.title for n in news]
    
    # [PIVOT 2] K-Deal 데이터 추출 (auto_collector에서 넘겨준 실데이터)
    k_deals = record.get("k_deals", {}).get("deals", [])
    fx_rate = record.get('usd_krw',{}).get('rate', 'N/A')
    wti_price = record.get('wti_crude',{}).get('price', 'N/A')
    
    prompt = f"""당신은 B2A 역직구 전략 오라클입니다. 
    시장수치: 환율 {fx_rate}원, 유가 {wti_price}달러
    최신뉴스: {headlines}
    수집된 한국 핫딜(K-Deals): {k_deals}
    
    위 데이터를 분석하여 '역직구(한국->해외) 마진'이 가장 좋은 상품을 하나 찾아 JSON으로만 답하세요.
    반드시 다음 포맷을 지키세요:
    {{ 
      "signal": "CLEAR" 혹은 "RESTRICTED", 
      "confidence": 0-100, 
      "target_item": "가장 수익성 높은 상품명 (없으면 null)",
      "reason": "해당 상품을 선택한 이유와 예상 마진에 대한 한 문장 분석" 
    }}
    """
    
    # 🧠 폭포수 생존 로직 (지휘관님 원본 유지)
    try:
        available_models = [m.name for m in client.models.list() if "gemini" in m.name and "flash" in m.name]
        available_models.sort(reverse=True)
    except Exception:
        available_models = ["gemini-1.5-flash"]
        
    for model_id in available_models:
        clean_model_name = model_id.replace("models/", "")
        try:
            response = client.models.generate_content(model=clean_model_name, contents=prompt)
            res_json = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            
            # 확신도가 낮거나 추천 상품이 없으면 방어 태세 전환
            if res_json.get('confidence', 0) < CONFIDENCE_THRESHOLD or not res_json.get('target_item'): 
                res_json['signal'] = "STANDBY"
            
            # RSA 서명 날인
            payload_str = json.dumps(res_json, sort_keys=True)
            sig, pub = generate_rsa_signature(payload_str)
            res_json.update({"rsa_sig": sig, "timestamp": datetime.datetime.now().isoformat()})
            
            # 감사 로그 기록
            with open(AUDIT_LOG_FILE, "a") as f: f.write(json.dumps(res_json) + "\n")
            
            # 최종 결과 출력 형식 개선 (트위터 봇이 읽기 쉽게)
            return f"[{res_json['signal']}] 타겟: {res_json.get('target_item', 'None')} | 분석: {res_json['reason']} (Verified by {clean_model_name})"
            
        except Exception as e:
            if "404" in str(e) or "not available" in str(e).lower():
                continue
            else:
                return f"STANDBY - Engine Sync Error: {str(e)}"
                
    return "STANDBY - No available Gemini Flash models found."
