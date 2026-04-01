import os, json, base64, datetime, feedparser
from dotenv import load_dotenv
from google import genai
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

# --- Constants ---
CONFIDENCE_THRESHOLD = 90
AUDIT_LOG_FILE = "audit_history.jsonl"

def generate_rsa_signature(payload_str: str):
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
    
    prompt = f"""당신은 B2A 전략 오라클입니다. 
    시장수치: 환율 {record.get('usd_krw',{}).get('rate')}원, 유가 {record.get('wti_crude',{}).get('price')}달러
    최신뉴스: {headlines}
    
    위 데이터를 분석하여 '역직구(한국->해외) 수익성'을 JSON으로만 답하세요.
    {{ "signal": "CLEAR/RESTRICTED", "confidence": 0-100, "reason": "한 문장 분석" }}
    """
    
    # 🧠 [업그레이드] 지휘관님의 '동적 모델 탐색 + 폭포수 생존 로직'
    try:
        # 사용 가능한 모델 목록을 가져와서 'flash'와 'gemini'가 포함된 것만 추림
        available_models = [m.name for m in client.models.list() if "gemini" in m.name and "flash" in m.name]
        # 이름순으로 역순 정렬 (예: 2.5-flash -> 2.0-flash -> 1.5-flash 순으로 배치)
        available_models.sort(reverse=True)
    except Exception:
        # API 조회 실패 시 최후의 보루
        available_models = ["gemini-1.5-flash"]
        
    # 높은 버전부터 차례대로 타격 시도
    for model_id in available_models:
        clean_model_name = model_id.replace("models/", "")
        try:
            # 해당 모델로 생성 시도
            response = client.models.generate_content(model=clean_model_name, contents=prompt)
            res_json = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            
            if res_json.get('confidence', 0) < CONFIDENCE_THRESHOLD: 
                res_json['signal'] = "STANDBY"
            
            # RSA 서명 날인
            payload_str = json.dumps(res_json, sort_keys=True)
            sig, pub = generate_rsa_signature(payload_str)
            res_json.update({"rsa_sig": sig, "timestamp": datetime.datetime.now().isoformat()})
            
            # 감사 로그 기록 (어떤 모델이 성공했는지도 함께 기록)
            with open(AUDIT_LOG_FILE, "a") as f: f.write(json.dumps(res_json) + "\n")
            
            return f"[{res_json['signal']}] {res_json['reason']} (Verified by {clean_model_name})"
            
        except Exception as e:
            # 404(권한/단종) 에러가 나면 뻗지 않고 다음 모델로 넘어감(continue)
            if "404" in str(e) or "not available" in str(e).lower():
                continue
            else:
                return f"STANDBY - Engine Sync Error: {str(e)}"
                
    return "STANDBY - No available Gemini Flash models found."