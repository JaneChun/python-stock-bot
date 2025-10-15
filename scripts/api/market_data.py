"""
시장 데이터 조회 API
"""
from datetime import datetime
from .utils import safe_int, safe_float


def get_current_price(kiwoom, code):
    """
    현재가 조회

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드

    Returns:
        dict: 현재가 정보 (종목명, 현재가, 등락률 등)
    """
    try:
        data = kiwoom.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        # DataFrame 처리
        if data is None or data.empty:
            return None

        if '현재가' not in data.columns:
            return None

        name = data['종목명'].iloc[0] if '종목명' in data.columns else code
        current_price = safe_int(data['현재가'].iloc[0], use_abs=True) if '현재가' in data.columns else 0

        return {
            'code': code,
            'name': name,
            'current_price': current_price,
            'data': data.to_dict('records')[0] if not data.empty else {}
        }

    except Exception as e:
        print(f"[오류] {code} 현재가 조회 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_stock_info(kiwoom, code):
    """
    종목 상세 정보 조회 (거래량, 거래대금 등)

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드

    Returns:
        dict: 종목 정보
    """
    try:
        data = kiwoom.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        # DataFrame 처리
        if data is None or data.empty:
            return None

        return {
            'code': code,
            'name': data['종목명'].iloc[0] if '종목명' in data.columns else code,
            'current_price': safe_int(data['현재가'].iloc[0], use_abs=True) if '현재가' in data.columns else 0,
            'volume': safe_int(data['거래량'].iloc[0], use_abs=True) if '거래량' in data.columns else 0,
            'open': safe_int(data['시가'].iloc[0], use_abs=True) if '시가' in data.columns else 0,
            'high': safe_int(data['고가'].iloc[0], use_abs=True) if '고가' in data.columns else 0,
            'low': safe_int(data['저가'].iloc[0], use_abs=True) if '저가' in data.columns else 0,
        }

    except Exception as e:
        print(f"[오류] {code} 정보 조회 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_daily_data(kiwoom, code, days=20):
    """
    일봉 데이터 조회

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        days: 조회 일수

    Returns:
        list: 일봉 데이터 리스트
    """
    try:
        data = kiwoom.block_request(
            "opt10081",
            종목코드=code,
            기준일자=datetime.now().strftime('%Y%m%d'),
            수정주가구분="1",
            output="주식일봉차트조회",
            next=0
        )

        # DataFrame 처리
        if data is None or data.empty:
            return []

        if '현재가' not in data.columns:
            return []

        daily_data = []
        length = min(len(data), days)

        for i in range(length):
            daily_data.append({
                'date': data['일자'].iloc[i] if '일자' in data.columns else '',
                'open': safe_int(data['시가'].iloc[i], use_abs=True) if '시가' in data.columns else 0,
                'high': safe_int(data['고가'].iloc[i], use_abs=True) if '고가' in data.columns else 0,
                'low': safe_int(data['저가'].iloc[i], use_abs=True) if '저가' in data.columns else 0,
                'close': safe_int(data['현재가'].iloc[i], use_abs=True) if '현재가' in data.columns else 0,
                'volume': safe_int(data['거래량'].iloc[i], use_abs=True) if '거래량' in data.columns else 0,
                'trading_value': safe_int(data['거래대금'].iloc[i], use_abs=True) if '거래대금' in data.columns else 0,
            })

        return daily_data

    except Exception as e:
        print(f"[오류] {code} 일봉 데이터 조회 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_investor_data(kiwoom, code):
    """
    외국인/기관 매매 정보 조회

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드

    Returns:
        dict: 외국인/기관 순매수 정보
    """
    try:
        # 일자별 매매 정보 조회
        data = kiwoom.block_request(
            "opt10059",
            # 일자=datetime.now().strftime('%Y%m%d'),
            일자='20251014',
            종목코드=code,
            금액수량구분="1",  # 1:금액, 2:수량
            매매구분="0",     # 0:순매수, 1:매수, 2:매도
            단위구분="1000",  # 1:단주, 1000:천주
            output="종목별투자자기관별",
            next=0
        )

        # DataFrame 처리
        if data is None or data.empty:
            return None

        # 최근 데이터 사용 (첫 번째 행)
        return {
            'code': code,
            'date': data['일자'].iloc[0] if '일자' in data.columns else '',
            'foreigner': safe_int(data['외국인투자자'].iloc[0]) if '외국인투자자' in data.columns else 0,
            'institution': safe_int(data['기관계'].iloc[0]) if '기관계' in data.columns else 0,
            'price_change': safe_int(data['전일대비'].iloc[0]) if '전일대비' in data.columns else 0,
            'change_rate': safe_float(data['등락율'].iloc[0]) if '등락율' in data.columns else 0.0,
        }

    except Exception as e:
        print(f"[오류] {code} 투자자 정보 조회 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
