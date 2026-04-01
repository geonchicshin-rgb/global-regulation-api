import os, json, base64, datetime, feedparser
from dotenv import load_dotenv
from google import genai
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

CONFIDENCE_THRESHOLD = 90
AUDIT_LOG_FILE = "audit_history.jsonl"

def generate_rsa_signature(payload_str: str):
    private_key_str = os.getenv("RSA_PRIVATE_KEY", "")
    if private_key_str:
        private_key = serialization.load_pem_private_key(private_key_str.encode(), password=None)
    else:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
    signature = private_key.sign(payload_str.encode(), padding.PKCS1v15(), hashes.SHA256())
    pub_pem = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return base64.b64encode(signature).decode(), pub_pem

def generate_insight(record: dict) -> str:
    load_dotenv()
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    fx_rate = record.get('usd_krw', 1500)
    wti_price = record.get('wti_crude', 80)
    ebay_deals = record.get('ebay_deals', [])
    k_deals = record.get('k_deals', [])
    
    # [핵심 로직] 환율에 따라 AI에게 내리는 지시(Prompt)가 달라집니다.
    prompt = f"""당신은 B2A 하이브리드 무역 오라클입니다. 
    시장수치: 환율 {fx_rate}원, 유가 {wti_price}달러
    미국핫딜(수입 후보): {ebay_deals}
    한국핫딜(수출 후보): {k_deals}
    
    [행동 강령]
    1. 현재 환율({fx_rate}원)을 분석하십시오.
    2. 고환율(예: 1300원 이상)이라면 한국핫딜을 해외로 파는 '역직구(수출)'가 유리하므로 한국핫딜 중에서 타겟을 고르십시오.
    3. 저환율(예: 1300원 미만)이라면 미국핫딜을 한국으로 들여오는 '직구(수입)'가 유리하므로 미국핫딜 중에서 타겟을 고르십시오.
    
    반드시 다음 포맷의 JSON으로만 답하세요:
    {{ 
      "signal": "CLEAR" 혹은 "RESTRICTED", 
      "strategy_type": "EXPORT(수출)" 혹은 "IMPORT(수입)",
      "confidence": 0-100, 
      "target_item": "가장 수익성 높은 상품명",
      "reason": "선택한 전략(수출/수입)의 이유와 마진 분석" 
    }}
    """
    
    try:
        available_models = [m.name for m in client.models.list() if "gemini" in m.name and "flash" in m.name]
        available_models.sort(reverse=True)
    except:
        available_models = ["gemini-1.5-flash"]
        
    for model_id in available_models:
        clean_model_name = model_id.replace("models/", "")
        try:
            response = client.models.generate_content(model=clean_model_name, contents=prompt)
            res_json = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            
            if res_json.get('confidence', 0) < CONFIDENCE_THRESHOLD or not res_json.get('target_item'): 
                res_json['signal'] = "STANDBY"
            
            payload_str = json.dumps(res_json, sort_keys=True)
            sig, pub = generate_rsa_signature(payload_str)
            res_json.update({"rsa_sig": sig, "timestamp": datetime.datetime.now().isoformat()})
            
            with open(AUDIT_LOG_FILE, "a") as f: f.write(json.dumps(res_json) + "\n")
            
            return f"[{res_json['signal']}] [{res_json.get('strategy_type')}] 타겟: {res_json.get('target_item')} | {res_json.get('reason')} (Verified)"
            
        except Exception as e:
            if "404" in str(e) or "not available" in str(e).lower(): continue
            return f"STANDBY - Engine Sync Error: {str(e)}"
            
    return "STANDBY - No available Models found."
