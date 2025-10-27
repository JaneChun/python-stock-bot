"""
종목 필터링 API
- 거래량 폭증
- 외국인/기관 순매수
- 장대양봉
- 프로그램 매매 순매수
- 전고점 돌파/신고가
"""
from datetime import datetime
from pykrx import stock
from .market_data import get_daily_data, get_investor_data, get_stock_info, get_minute_data, get_trader_buy_sell
from .screening import screen_by_program
from .utils import safe_int
from .utils.rate_limiter import apply_rate_limit


def filter_by_volume_above_ma5_20_60(kiwoom, code_list):
    """
    거래량 폭증 종목 필터링 (5일, 20일, 60일 이동평균선 기준)

    종목 리스트를 받아 오늘 거래량이 5일, 20일, 60일 이동평균선을 모두 넘는 종목만 필터링합니다.

    Args:
        kiwoom: Kiwoom API 인스턴스
        code_list: 필터링할 종목코드 리스트

    Returns:
        list: 조건을 만족하는 종목코드 리스트
    """

    filtered_codes = []

    print(f"[거래량 MA5/20/60 필터링] {len(code_list)}개 종목 필터링 중...")

    for code in code_list:
        try:
            # API 호출 제한 적용
            is_passed, message = apply_rate_limit(
                lambda: _check_volume_above_ma5_20_60(kiwoom, code)
            )

            if is_passed:
                filtered_codes.append(code)

        except Exception as e:
            print(f"  ✗ {code}: 오류 - {str(e)}")

    print(f"[거래량 MA5/20/60 필터링] {len(filtered_codes)}개 종목 통과")
    return filtered_codes


def _check_volume_above_ma5_20_60(kiwoom, code):
    """
    단일 종목의 거래량 폭증 여부 확인 (내부 함수)

    오늘 거래량이 5일, 20일, 60일 이동평균선을 모두 넘는지 확인합니다.

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드

    Returns:
        tuple: (통과 여부, 상세 정보)
    """
    try:
        # 일봉 데이터 조회 (60일 + 오늘)
        daily_data = get_daily_data(kiwoom, code, 61)

        if len(daily_data) < 61:
            return False, "데이터 부족"

        # 오늘 데이터
        today = daily_data[0]
        today_volume = today['volume']

        # 5일, 20일, 60일 이동평균 계산 (오늘 제외, 과거 데이터)
        past_volumes = [d['volume'] for d in daily_data[1:]]

        # 5일 이동평균
        ma_5_volumes = past_volumes[:5]
        ma_5 = sum(ma_5_volumes) / \
            len(ma_5_volumes) if len(ma_5_volumes) == 5 else 0

        # 20일 이동평균
        ma_20_volumes = past_volumes[:20]
        ma_20 = sum(ma_20_volumes) / \
            len(ma_20_volumes) if len(ma_20_volumes) == 20 else 0

        # 60일 이동평균
        ma_60_volumes = past_volumes[:60]
        ma_60 = sum(ma_60_volumes) / \
            len(ma_60_volumes) if len(ma_60_volumes) == 60 else 0

        if ma_5 == 0 or ma_20 == 0 or ma_60 == 0:
            return False, "평균 거래량 계산 실패"

        # 각 이동평균선 대비 비율
        ratio_5 = today_volume / ma_5
        ratio_20 = today_volume / ma_20
        ratio_60 = today_volume / ma_60

        # 오늘 거래량이 5일, 20일, 60일 이동평균선을 모두 넘었는지 확인
        if today_volume > ma_5 and today_volume > ma_20 and today_volume > ma_60:
            return True, f"거래량 폭증 (거래량 {today_volume:,} > MA5 {ma_5:,.0f}({ratio_5:.2f}배), MA20 {ma_20:,.0f}({ratio_20:.2f}배), MA60 {ma_60:,.0f}({ratio_60:.2f}배))"
        else:
            failed = []
            if today_volume <= ma_5:
                failed.append(f"MA5 {ma_5:,.0f}({ratio_5:.2f}배)")
            if today_volume <= ma_20:
                failed.append(f"MA20 {ma_20:,.0f}({ratio_20:.2f}배)")
            if today_volume <= ma_60:
                failed.append(f"MA60 {ma_60:,.0f}({ratio_60:.2f}배)")
            return False, f"거래량 부족 (거래량 {today_volume:,}, 미달: {', '.join(failed)})"

    except Exception as e:
        return False, f"오류: {str(e)}"


def filter_by_volume_and_change(kiwoom, code_list, ma_period=5, volume_multiplier=3, min_change_ratio=0.0):
    """
    거래량 폭증 종목 필터링 (이동평균 기준 + 상승률 조건)

    종목 리스트를 받아 다음 조건을 모두 만족하는 종목만 필터링합니다:
    1. 오늘 거래량이 지정한 기간의 이동평균 대비 지정한 배수를 초과
    2. 오늘 상승률이 지정한 기준 이상

    Args:
        kiwoom: Kiwoom API 인스턴스
        code_list: 필터링할 종목코드 리스트
        ma_period (int, optional): 이동평균 계산 기간 (기본값: 5일)
        volume_multiplier (float, optional): 거래량 배수 기준 (기본값: 3배)
        min_change_ratio (float, optional): 최소 상승률 (기본값: 0.0 = 0%)

    Returns:
        list: 조건을 만족하는 종목코드 리스트
    """
    from .utils.rate_limiter import apply_rate_limit

    filtered_codes = []

    print(
        f"[거래량+상승률 필터링] MA{ma_period}의 {volume_multiplier}배, 상승률 {min_change_ratio*100:.0f}% 기준으로 {len(code_list)}개 종목 필터링 중...")

    for code in code_list:
        try:
            # API 호출 제한 적용
            is_passed, message = apply_rate_limit(
                lambda: _check_volume_and_change(
                    kiwoom, code, ma_period, volume_multiplier, min_change_ratio)
            )

            if is_passed:
                filtered_codes.append(code)

        except Exception as e:
            print(f"  ✗ {code}: 오류 - {str(e)}")

    print(f"[거래량+상승률 필터링] {len(filtered_codes)}개 종목 통과")
    return filtered_codes


def _check_volume_and_change(kiwoom, code, ma_period, volume_multiplier, min_change_ratio):
    """
    단일 종목의 거래량 폭증 및 상승률 확인 (내부 함수)

    다음 조건을 순차적으로 확인하여 모두 통과해야 합니다:
    1. 오늘 상승률이 최소 기준 이상인지 확인
    2. 오늘 거래량이 이동평균선의 지정 배수를 초과하는지 확인

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        ma_period: 이동평균 계산 기간
        volume_multiplier: 거래량 배수 기준
        min_change_ratio: 최소 상승률 (예: 0.03 = 3%)

    Returns:
        tuple: (통과 여부, 상세 정보)
    """
    try:
        # 일봉 데이터 조회 (지정 기간 + 오늘)
        daily_data = get_daily_data(kiwoom, code, ma_period + 1)

        if len(daily_data) < ma_period + 1:
            return False, "데이터 부족"

        # 오늘 데이터
        today = daily_data[0]
        today_volume = today['volume']

        # 상승률 계산: 현재가 - 시가 / 시가
        open_price = today['open']
        close_price = today['close']
        change_ratio = (close_price - open_price) / open_price

        # 상승률 기준 체크
        if change_ratio < min_change_ratio:
            return False, f"상승률 기준 미달 (상승률 {change_ratio*100:.1f}%)"

        # 이동평균 계산 (오늘 제외, 과거 데이터)
        past_volumes = [d['volume'] for d in daily_data[1:]]

        # 지정 기간 이동평균
        ma_volumes = past_volumes[:ma_period]
        ma = sum(ma_volumes) / \
            len(ma_volumes) if len(ma_volumes) == ma_period else 0

        if ma == 0:
            return False, "평균 거래량 계산 실패"

        # 이동평균선 대비 비율
        ratio = today_volume / ma

        # 오늘 거래량이 이동평균선의 지정 배수를 넘었는지 확인
        if today_volume > ma * volume_multiplier:
            return True, f"거래량 {today_volume:,} (MA{ma_period} {ma:,.0f}의 {ratio:.2f}배)"
        else:
            return False, f"거래량 {today_volume:,} (MA{ma_period} {ma:,.0f}의 {ratio:.2f}배, 기준: {volume_multiplier}배)"

    except Exception as e:
        return False, f"오류: {str(e)}"


def filter_by_program(kiwoom, code_list, count=50):
    """
    프로그램 순매수 상위 종목에 포함되는 종목만 필터링 (코스피 + 코스닥 통합)

    Args:
        kiwoom: Kiwoom API 인스턴스
        code_list: 필터링할 종목코드 리스트
        count: 조회할 상위 종목 수 (기본값: 50)

    Returns:
        list: 프로그램 순매수 상위 종목에 포함되는 종목코드 리스트
    """
    try:
        # 프로그램 순매수 상위 종목 조회 (코스피 + 코스닥)
        top_codes = screen_by_program(kiwoom, count)

        if not top_codes:
            print(f"[오류] 프로그램 순매수 상위 종목 조회 실패")
            return []

        # 입력 종목 중 상위 종목에 포함된 종목만 필터링
        filtered_codes = [code for code in code_list if code in top_codes]

        print(
            f"[프로그램 순매수 필터링] 입력: {len(code_list)}개, 상위 종목 포함: {len(filtered_codes)}개")

        return filtered_codes

    except Exception as e:
        print(f"[오류] 프로그램 순매수 필터링 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def get_program_rank(kiwoom, code: str, program_count: int) -> int:
    """
    프로그램 순매수 순위 조회

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        program_count: 상위 몇 개까지 조회할지

    Returns:
        int: 순위 (1부터 시작), 순위권 밖이거나 조회 실패시 -1
    """
    try:
        program_top_codes = screen_by_program(kiwoom, program_count)
        if code in program_top_codes:
            return program_top_codes.index(code) + 1
    except Exception:
        pass
    return -1


def check_ma_alignment(kiwoom, code: str, tick: int = 3, periods: list = [5, 10, 20, 60]) -> bool:
    """
    이동평균선 정배열 체크

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        tick: 분봉 틱 (기본값: 3분봉)
        periods: 이동평균 기간 리스트 (기본값: [5, 10, 20, 60])
                예: [10, 20] → MA10 >= MA20
                    [10, 20, 40] → MA10 >= MA20 >= MA40
                    [5, 10, 20, 60] → MA5 >= MA10 >= MA20 >= MA60

    Returns:
        bool: 정배열이면 True, 아니면 False
    """
    # 입력 검증
    if not periods or len(periods) < 2:
        print(f"[MA정배열 체크] {code}: 입력 검증 실패 (periods={periods})")
        return False

    # 필요한 최대 캔들 개수
    max_period = max(periods)

    # 캔들 데이터 조회
    minute_data = get_minute_data(kiwoom, code, tick=tick, count=max_period)

    # 데이터가 충분하지 않으면 False
    if len(minute_data) < max_period:
        print(
            f"[MA정배열 체크] {code}: 데이터 부족 (필요: {max_period}개, 실제: {len(minute_data)}개)")
        return False

    # 종가 추출 (최신 데이터가 앞에 있으므로)
    closes = [candle['close'] for candle in minute_data]

    # 각 기간별 이동평균 계산
    moving_averages = []
    for period in periods:
        ma = sum(closes[:period]) / period
        moving_averages.append(ma)

    # 정배열 체크: MA[0] >= MA[1] >= ... >= MA[n]
    for i in range(len(moving_averages) - 1):
        if moving_averages[i] < moving_averages[i + 1]:
            print(
                f"[MA정배열 체크] {code}: 정배열 실패 (MA{periods[i]}={moving_averages[i]:.2f} < MA{periods[i+1]}={moving_averages[i+1]:.2f})")
            return False

    print(
        f"[MA정배열 체크] {code}: 정배열 통과 {dict(zip([f'MA{p}' for p in periods], [f'{ma:.2f}' for ma in moving_averages]))}")
    return True


def check_trader_sell_dominance(kiwoom, code: str, trader_code: str) -> bool:
    """
    특정 증권사의 매도량이 매수량보다 많은지 확인

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        trader_name: 증권사코드 (예: '050': 키움증권)

    Returns:
        bool: 매도량 > 매수량이면 True, 아니면 False
    """
    try:
        # 거래원 데이터 조회
        data = get_trader_buy_sell(kiwoom, code)

        if trader_code not in data:
            print(f"[거래원 체크] {code}: 거래원 코드 '{trader_code}' 정보 없음")
            return False

        trader_info = data[trader_code]
        trader_name = trader_info['name']
        sell = trader_info['sell']
        buy = trader_info['buy']

        print(
            f"[거래원 체크] {code} - {trader_name}: 매도 {sell if sell != 0 else '정보없음'}, 매수 {buy if buy != 0 else '정보없음'}")

        return sell > buy

    except Exception as e:
        print(f"[오류] {code} 거래원 체크 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# def filter_by_breakout(kiwoom, code, lookback_days=5, near_high_ratio=0.98):
#     """
#     전고점 돌파 또는 신고가 여부 확인

#     Args:
#         kiwoom: Kiwoom API 인스턴스
#         code: 종목코드
#         lookback_days: 과거 조회 기간 (기본값: 5일)
#         near_high_ratio: 고점 근접 비율 (기본값: 0.98 = 98%, 고점의 98% 이상이면 통과)

#     Returns:
#         tuple: (통과 여부, 상세 정보)
#     """
#     try:
#         # 일봉 데이터 조회
#         daily_data = get_daily_data(kiwoom, code, lookback_days + 1)

#         if len(daily_data) < 2:
#             return False, "데이터 부족"

#         # 현재가
#         current_price = daily_data[0]['close']

#         # 과거 N일간 최고가
#         past_highs = [d['high'] for d in daily_data[1:]]
#         max_high = max(past_highs) if past_highs else 0

#         if max_high == 0:
#             return False, "과거 최고가 없음"

#         # 현재가가 과거 최고가 돌파 또는 근접
#         if current_price >= max_high:
#             return True, f"신고가 돌파 (현재가 {current_price:,} vs 과거고점 {max_high:,})"
#         elif current_price >= max_high * near_high_ratio:
#             ratio = current_price / max_high
#             return True, f"고점 근접 (현재가 {current_price:,}, 고점 대비 {ratio*100:.1f}%)"
#         else:
#             ratio = current_price / max_high
#             return False, f"고점 미도달 (현재가 {current_price:,}, 고점 대비 {ratio*100:.1f}%)"

#     except Exception as e:
#         return False, f"오류: {str(e)}"


# def apply_all_filters(kiwoom, code,
#                       min_net_buy=0,
#                       min_body_ratio=0.6,
#                       min_change_ratio=0.03,
#                       lookback_days=5,
#                       near_high_ratio=0.98):
#     """
#     모든 필터를 한 번에 적용

#     Args:
#         kiwoom: Kiwoom API 인스턴스
#         code: 종목코드
#         기타 파라미터: 각 필터의 파라미터

#     Returns:
#         dict: 각 필터의 결과
#     """
#     results = {
#         'code': code,
#         'volume': filter_by_trading_volume(kiwoom, code),
#         'institutional': filter_by_institutional_buying(kiwoom, code, min_net_buy),
#         'candle': filter_by_long_candle(kiwoom, code, min_body_ratio, min_change_ratio),
#         'breakout': filter_by_breakout(kiwoom, code, lookback_days, near_high_ratio),
#     }

#     # 모든 필터 통과 여부
#     results['pass_all'] = all([
#         results['volume'][0],
#         results['institutional'][0],
#         results['candle'][0],
#         results['breakout'][0],
#     ])

#     return results
