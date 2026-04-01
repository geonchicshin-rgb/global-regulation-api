"""
shipping_calculator.py
- [하이브리드 B2A 물류 엔진] 수입(Import) 및 수출(Export) 동적 운송료 계산기
"""

def calculate_import_cost(usd_price: float, weight_lbs: float, fx_rate: float, wti_price: float) -> dict:
    """ 해외 물건을 한국으로 들여올 때의 원화(KRW) 도착가 계산 """
    try:
        base_shipping_usd = 12.0 + (max(0, weight_lbs - 1.0) * 2.5)
        oil_surcharge_pct = max(0, (wti_price - 75.0) * 0.005)
        total_shipping_usd = base_shipping_usd * (1 + oil_surcharge_pct)
        
        total_value_usd = usd_price + total_shipping_usd
        tax_usd = total_value_usd * 0.188 if total_value_usd > 200.0 else 0.0 # 한국 목록통관 한도
            
        final_krw = (total_value_usd + tax_usd) * fx_rate
        return {"status": "OK", "final_krw": round(final_krw, 0), "type": "IMPORT"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

def calculate_export_cost(krw_price: float, weight_kg: float, fx_rate: float, wti_price: float) -> dict:
    """ 한국 물건을 미국으로 수출할 때의 달러(USD) 손익분기점 계산 """
    try:
        item_cost_usd = krw_price / fx_rate # 고환율 시 달러 원가 압축
        
        base_shipping_usd = 8.0 + (weight_kg * 6.0) # 우체국 소형포장물 기준
        oil_surcharge_pct = max(0, (wti_price - 75.0) * 0.005)
        total_shipping_usd = base_shipping_usd * (1 + oil_surcharge_pct)
        
        total_value_usd = item_cost_usd + total_shipping_usd
        tax_usd = total_value_usd * 0.10 if total_value_usd > 800.0 else 0.0 # 미국 De Minimis 한도
            
        breakeven_usd = total_value_usd + tax_usd
        return {"status": "OK", "breakeven_usd": round(breakeven_usd, 2), "type": "EXPORT"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}
