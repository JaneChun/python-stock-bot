"""
시장 데이터 조회 API
"""
from datetime import datetime
from .utils import safe_int, safe_float, apply_rate_limit
import traceback
from collections import defaultdict


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
        data = apply_rate_limit(
            lambda: kiwoom.block_request(
                "opt10001",
                종목코드=code,
                output="주식기본정보",
                next=0
            ),
            delay=0.2
        )

        # DataFrame 처리
        if data is None or data.empty:
            return None

        if '현재가' not in data.columns:
            return None

        name = data['종목명'].iloc[0] if '종목명' in data.columns else code
        current_price = safe_int(
            data['현재가'].iloc[0], use_abs=True) if '현재가' in data.columns else None

        # 필수 데이터가 None인 경우 None 반환
        if current_price is None:
            print(f"[오류] {code} 현재가 데이터 변환 실패")
            return None

        return {
            'code': code,
            'name': name,
            'current_price': current_price,
            'data': data.to_dict('records')[0] if not data.empty else {}
        }

    except Exception as e:
        print(f"[오류] {code} 현재가 조회 실패: {str(e)}")
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
        data = apply_rate_limit(
            lambda: kiwoom.block_request(
                "opt10001",
                종목코드=code,
                output="주식기본정보",
                next=0
            ),
            delay=0.2
        )

        # DataFrame 처리
        if data is None or data.empty:
            return None

        # 필수 데이터 변환
        current_price = safe_int(
            data['현재가'].iloc[0], use_abs=True) if '현재가' in data.columns else None
        change_rate = safe_float(
            data['등락율'].iloc[0]) if '등락율' in data.columns else None
        price_change = safe_int(
            data['전일대비'].iloc[0]) if '전일대비' in data.columns else None
        volume = safe_int(data['거래량'].iloc[0],
                          use_abs=True) if '거래량' in data.columns else None
        open_price = safe_int(
            data['시가'].iloc[0], use_abs=True) if '시가' in data.columns else None
        high = safe_int(data['고가'].iloc[0],
                        use_abs=True) if '고가' in data.columns else None
        low = safe_int(data['저가'].iloc[0],
                       use_abs=True) if '저가' in data.columns else None

        # 필수 데이터가 None인 경우 None 반환
        if current_price is None or change_rate is None or volume is None or open_price is None or high is None or low is None:
            print(f"[오류] {code} 종목 정보 데이터 변환 실패")
            return None

        return {
            'code': code,
            'name': data['종목명'].iloc[0] if '종목명' in data.columns else code,
            'change_rate': change_rate,
            'price_change': price_change,
            'current_price': current_price,
            'volume': volume,
            'open': open_price,
            'high': high,
            'low': low,
        }

    except Exception as e:
        print(f"[오류] {code} 정보 조회 실패: {str(e)}")
        traceback.print_exc()
        return None


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
        data = apply_rate_limit(
            lambda: kiwoom.block_request(
                "opt10059",
                일자=datetime.now().strftime('%Y%m%d'),
                종목코드=code,
                금액수량구분="1",  # 1:금액, 2:수량
                매매구분="0",     # 0:순매수, 1:매수, 2:매도
                단위구분="1000",  # 1:단주, 1000:천주
                output="종목별투자자기관별",
                next=0
            ),
            delay=0.2
        )

        # DataFrame 처리
        if data is None or data.empty:
            return None

        # 필수 데이터 변환
        foreigner = safe_int(data['외국인투자자'].iloc[0]
                             ) if '외국인투자자' in data.columns else None
        institution = safe_int(
            data['기관계'].iloc[0]) if '기관계' in data.columns else None
        price_change = safe_int(
            data['전일대비'].iloc[0]) if '전일대비' in data.columns else None
        change_rate = safe_float(
            data['등락율'].iloc[0]) if '등락율' in data.columns else None

        # 필수 데이터가 None인 경우 None 반환
        if foreigner is None or institution is None or price_change is None or change_rate is None:
            print(f"[오류] {code} 투자자 정보 데이터 변환 실패")
            return None

        # 최근 데이터 사용 (첫 번째 행)
        return {
            'code': code,
            'date': data['일자'].iloc[0] if '일자' in data.columns else '',
            'foreigner': foreigner,
            'institution': institution,
            'price_change': price_change,
            'change_rate': change_rate,
        }

    except Exception as e:
        print(f"[오류] {code} 투자자 정보 조회 실패: {str(e)}")
        traceback.print_exc()
        return None


def get_trader_buy_sell(kiwoom, code):
    """
    당일 주요 거래원 정보 조회

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드

    Returns:
        dict: 거래원 코드를 키로 하는 딕셔너리
              예: {'050': {'name': '키움증권', 'sell': 1000, 'buy': 500}, ...}
              조회 실패시 None 반환
    """
    try:
        data = apply_rate_limit(
            lambda: kiwoom.block_request(
                "opt10040",
                종목코드=code,
                output="당일주요거래원싱글",
                next=0
            ),
            delay=0.2
        )

        if data is None or data.empty:
            return None

        traders = defaultdict(lambda: {'name': '', 'sell': 0, 'buy': 0})

        # 매도 거래원
        sell_code_cols = [
            col for col in data.columns if col.startswith('매도거래원코드')]

        for code_col in sell_code_cols:
            # 거래원 코드 추출
            # 매도거래원코드1, 매도거래원코드2, ...
            trader_code = str(data[code_col].iloc[0]).strip()
            if not trader_code or trader_code == '' or trader_code == 'nan':
                continue

            # 거래원 코드에 대응하는 거래원명 찾기
            name_col = code_col.replace('코드', '')  # 매도거래원1, 매도거래원2, ...
            trader_name = data[name_col].iloc[0].strip()

            # 대응하는 수량 찾기
            # 매도거래원수량1, 매도거래원수량2, ...
            volume_col = code_col.replace('코드', '수량')
            sell_volume = safe_int(data[volume_col].iloc[0], use_abs=True)

            # 딕셔너리에 추가/업데이트
            traders[trader_code]['name'] = trader_name
            traders[trader_code]['sell'] = sell_volume

        # 매수 거래원
        buy_code_cols = [
            col for col in data.columns if col.startswith('매수거래원코드')]

        for code_col in buy_code_cols:
            trader_code = str(data[code_col].iloc[0]).strip()
            if not trader_code or trader_code == '' or trader_code == 'nan':
                continue

            name_col = code_col.replace('코드', '')
            trader_name = data[name_col].iloc[0].strip()

            volume_col = code_col.replace('코드', '수량')
            buy_volume = safe_int(data[volume_col].iloc[0], use_abs=True)

            traders[trader_code]['name'] = trader_name
            traders[trader_code]['buy'] = buy_volume

        return traders

    except Exception as e:
        print(f"[오류] {code} 현재 거래원 정보 조회 실패: {str(e)}")
        traceback.print_exc()
        return None


def get_minute_data(kiwoom, code, tick=1, count=20):
    """
    분봉 데이터 조회

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        minutes: 조회 분수

    Returns:
        list: 분봉 데이터 리스트
    """
    try:
        data = apply_rate_limit(
            lambda: kiwoom.block_request(
                "opt10080",
                종목코드=code,
                틱범위=tick,  # 1:1분, 3:3분, 5:5분, 10:10분, 15:15분, 30:30분, 45:45분, 60:60분
                수정주가구분="1",
                output="주식분봉차트조회",
                next=0
            ),
            delay=0.2
        )

        # DataFrame 처리
        if data is None or data.empty:
            return []

        if '현재가' not in data.columns:
            return []

        minute_data = []
        length = min(len(data), count)

        for i in range(length):
            # 필수 데이터 변환
            time = data['체결시간'].iloc[i] if '체결시간' in data.columns else None
            open_price = safe_int(
                data['시가'].iloc[i], use_abs=True) if '시가' in data.columns else None
            high = safe_int(data['고가'].iloc[i],
                            use_abs=True) if '고가' in data.columns else None
            low = safe_int(data['저가'].iloc[i],
                           use_abs=True) if '저가' in data.columns else None
            close = safe_int(
                data['현재가'].iloc[i], use_abs=True) if '현재가' in data.columns else None
            volume = safe_int(
                data['거래량'].iloc[i], use_abs=True) if '거래량' in data.columns else None

            # None이 있는 경우 해당 데이터 스킵
            if time is None or open_price is None or high is None or low is None or close is None or volume is None:
                print(f"[분봉] {code} {i}번째 데이터 변환 실패로 스킵")
                continue

            minute_data.append({
                'time': time,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
            })

        return minute_data

    except Exception as e:
        print(f"[오류] {code} {tick}분봉 데이터 조회 실패: {str(e)}")
        traceback.print_exc()

    return []


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
        data = apply_rate_limit(
            lambda: kiwoom.block_request(
                "opt10081",
                종목코드=code,
                기준일자=datetime.now().strftime('%Y%m%d'),
                수정주가구분="1",
                output="주식일봉차트조회",
                next=0
            ),
            delay=0.2
        )

        # DataFrame 처리
        if data is None or data.empty:
            return []

        if '현재가' not in data.columns:
            return []

        daily_data = []
        length = min(len(data), days)

        for i in range(length):
            # 필수 데이터 변환
            date = data['일자'].iloc[i] if '일자' in data.columns else None
            open_price = safe_int(
                data['시가'].iloc[i], use_abs=True) if '시가' in data.columns else None
            high = safe_int(data['고가'].iloc[i],
                            use_abs=True) if '고가' in data.columns else None
            low = safe_int(data['저가'].iloc[i],
                           use_abs=True) if '저가' in data.columns else None
            close = safe_int(
                data['현재가'].iloc[i], use_abs=True) if '현재가' in data.columns else None
            volume = safe_int(
                data['거래량'].iloc[i], use_abs=True) if '거래량' in data.columns else None
            trading_value = safe_int(
                data['거래대금'].iloc[i], use_abs=True) if '거래대금' in data.columns else None

            # None이 있는 경우 해당 데이터 스킵
            if date is None or open_price is None or high is None or low is None or close is None or volume is None or trading_value is None:
                print(f"[일봉] {code} {i}번째 데이터 변환 실패로 스킵")
                continue

            daily_data.append({
                'date': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
                'trading_value': trading_value,
            })

        return daily_data

    except Exception as e:
        print(f"[오류] {code} 일봉 데이터 조회 실패: {str(e)}")
        traceback.print_exc()

    return []


def print_names(kiwoom, code_list):
    names = []
    for code in code_list:
        name = kiwoom.GetMasterCodeName(code)
        names.append(name)
    print(names)
