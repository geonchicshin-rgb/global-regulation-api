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
    
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        res_json = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        
        if res_json['confidence'] < CONFIDENCE_THRESHOLD: res_json['signal'] = "STANDBY"
        
        # 2. RSA 서명 날인
        payload_str = json.dumps(res_json, sort_keys=True)
        sig, pub = generate_rsa_signature(payload_str)
        res_json.update({"rsa_sig": sig, "timestamp": datetime.datetime.now().isoformat()})
        
        # 3. 감사 로그 기록
        with open(AUDIT_LOG_FILE, "a") as f: f.write(json.dumps(res_json) + "\n")
        
        return f"[{res_json['signal']}] {res_json['reason']} (Verified)"
    except Exception as e:
        return f"STANDBY - Engine Sync Error: {str(e)}"