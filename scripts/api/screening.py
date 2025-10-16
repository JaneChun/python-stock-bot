"""
종목 스크리닝 API (시가총액, 거래대금 기준)
"""
from datetime import datetime
from .utils import safe_int, safe_float


def screen_by_volume(kiwoom, market_type="000"):
    """
    거래대금 상위 종목 스크리닝

    Args:
        kiwoom: Kiwoom API 인스턴스
        market_type: 시장구분 (000:전체, 001:코스피, 101:코스닥)

    Returns:
        list: 종목 정보가 담긴 딕셔너리 리스트 (JSON 형태)
    """
    try:
        print(f"[스크리닝] 거래대금 상위 종목 조회 중... (시장구분: {market_type})")

        # OPT10032: 거래대금상위요청
        data = kiwoom.block_request(
            "opt10032",
            시장구분=market_type,      # 000:전체, 001:코스피, 101:코스닥
            관리종목포함="16",          # 0:미포함, 1:포함, 16:ETF+ETN제외
            거래소구분="",              # 공백: KRX
            output="거래대금상위",
            next=0
        )

        # DataFrame 처리
        if data is None or data.empty:
            print("[스크리닝] 조회된 데이터가 없습니다.")
            return []

        # ETF 제외
        etf = kiwoom.GetCodeListByMarket('8')

        stocks = []
        for i in range(len(data)):
            code = data['종목코드'].iloc[i].strip()
            if code in etf:
                continue

            # 필수 데이터 변환
            current_price = safe_int(
                data['현재가'].iloc[i]) if '현재가' in data.columns else None
            price_change = safe_int(
                data['전일대비'].iloc[i]) if '전일대비' in data.columns else None
            change_rate = safe_float(
                data['등락률'].iloc[i]) if '등락률' in data.columns else None
            trading_value = safe_int(
                data['거래대금'].iloc[i], use_abs=True) if '거래대금' in data.columns else None

            # None이 있는 경우 해당 데이터 스킵
            if current_price is None or price_change is None or change_rate is None or trading_value is None:
                print(f"[스크리닝] 데이터 변환 실패로 스킵: {code}")
                continue

            stocks.append({
                'code': data['종목코드'].iloc[i].strip() if '종목코드' in data.columns else '',
                'name': data['종목명'].iloc[i].strip() if '종목명' in data.columns else '',
                'current_price': current_price,
                'price_change': price_change,
                'price_change_sign': data['전일대비기호'].iloc[i].strip() if '전일대비기호' in data.columns else '',
                'change_rate': change_rate,
                'trading_value': trading_value
            })

        # 거래대금 기준 내림차순
        stocks.sort(key=lambda x: -x['trading_value'])

        print(f"[스크리닝] {len(stocks)}개 종목 조회됨")

        return stocks

    except Exception as e:
        print(f"[오류] 스크리닝 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
