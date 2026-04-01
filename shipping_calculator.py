"""
shipping_calculator.py
- 유가(WTI) 및 환율(FX) 연동 동적 운송료 계산 엔진
"""

def calculate_landed_cost(usd_price: float, weight_lbs: float, fx_rate: float, wti_price: float) -> dict:
    """
    상품 가격, 무게, 환율, 유가를 기반으로 한국 도착 최종 원화(KRW)를 계산합니다.
    """
    try:
        # 1. 기본 배송비: 기본 1lb $12, 추가 1lb당 $2.5 가정
        base_shipping_usd = 12.0 + (max(0, weight_lbs - 1.0) * 2.5)
        
        # 2. 유류할증료(Oil Surcharge): WTI $75 초과 시 1달러당 0.5% 할증 적용
        oil_surcharge_pct = max(0, (wti_price - 75.0) * 0.005)
        surcharge_usd = base_shipping_usd * oil_surcharge_pct
        total_shipping_usd = base_shipping_usd + surcharge_usd
        
        # 3. 과세 표준 금액 (물품가 + 배송비)
        total_value_usd = usd_price + total_shipping_usd
        
        # 4. 관부가세 계산 (목록통관 $200 초과 시 약 18.8% 적용)
        tax_usd = 0.0
        if total_value_usd > 200.0:
            tax_usd = total_value_usd * 0.188
            
        # 5. 최종 달러 및 원화 계산
        final_usd = total_value_usd + tax_usd
        final_krw = final_usd * fx_rate
        
        return {
            "status": "OK",
            "base_shipping_usd": round(base_shipping_usd, 2),
            "oil_surcharge_usd": round(surcharge_usd, 2),
            "tax_usd": round(tax_usd, 2),
            "final_usd": round(final_usd, 2),
            "final_krw": round(final_krw, 0)
        }
        
    except Exception as e:
        return {"status": "ERROR", "message": str(e), "final_krw": None}