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
from .market_data import get_daily_data, get_investor_data, get_stock_info
from .screening import get_program_top50_codes
from .utils import safe_int


def filter_by_volume_above_ma5_20_60(kiwoom, code):
    """
    거래량 폭증 여부 확인 (5일, 20일, 60일 이동평균선 기준)

    조건:
    1. 오늘 거래량이 5일, 20일, 60일 이동평균선을 모두 넘어야 함
    2. 매수세가 강해야 함 (종가 > 시가, 즉 양봉)

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
            return True, f"거래량 폭증 (거래량 {today_volume:,} > MA5 {ma_5:,.0f}({ratio_5:.2f}배), MA20 {ma_20:,.0f}({ratio_20:.2f}배), MA60 {ma_60:,.0f}({ratio_60:.2f}배)), 매수세"
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


def filter_by_volume_5x_ma5(kiwoom, code):
    """
    거래량 폭증 여부 확인 (5일 이동평균 기준)

    조건:
    1. 오늘 거래량이 과거 5일 평균 거래량의 5배를 초과해야 함
    2. 매수세가 강해야 함 (종가 > 시가, 즉 양봉)

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드

    Returns:
        tuple: (통과 여부, 상세 정보)
    """
    MA_PERIOD = 5
    VOLUME_MULTIPLIER = 5

    try:
        # 일봉 데이터 조회 (5일 + 오늘)
        daily_data = get_daily_data(kiwoom, code, MA_PERIOD + 1)

        if len(daily_data) < MA_PERIOD + 1:
            return False, "데이터 부족"

        # 오늘 데이터
        today = daily_data[0]
        today_volume = today['volume']

        # 5일 이동평균 계산 (오늘 제외, 과거 데이터)
        past_volumes = [d['volume'] for d in daily_data[1:]]

        # 5일 이동평균
        ma_5_volumes = past_volumes[:MA_PERIOD]
        ma_5 = sum(ma_5_volumes) / \
            len(ma_5_volumes) if len(ma_5_volumes) == MA_PERIOD else 0

        if ma_5 == 0:
            return False, "평균 거래량 계산 실패"

        # 각 이동평균선 대비 비율
        ratio_5 = today_volume / ma_5

        # 오늘 거래량이 5일 이동평균선의 5배를 넘었는지 확인
        if today_volume > ma_5 * VOLUME_MULTIPLIER:
            return True, f"거래량 폭증 (거래량 {today_volume:,} > MA{MA_PERIOD} {ma_5:,.0f}({ratio_5:.2f}배), 매수세"
        else:
            failed = []
            if today_volume <= ma_5:
                failed.append(f"MA{MA_PERIOD} {ma_5:,.0f}({ratio_5:.2f}배)")
            return False, f"거래량 부족 (거래량 {today_volume:,}, 미달: {', '.join(failed)})"

    except Exception as e:
        return False, f"오류: {str(e)}"


def filter_by_long_candle(kiwoom, code, min_body_ratio=0.7, min_change_ratio=0.03):
    """
    일봉이 장대양봉인지 확인

    Args:
        kiwoom: Kiwoom API 인스턴스
        code: 종목코드
        min_body_ratio: 최소 몸통 비율 (고가-저가 대비 종가-시가 비율, 기본값: 0.7 = 70%)
        min_change_ratio: 최소 상승률 (기본값: 0.03 = 3%)

    Returns:
        tuple: (통과 여부, 상세 정보)
    """
    try:
        # 오늘 데이터 조회
        daily_data = get_daily_data(kiwoom, code, 1)

        if not daily_data:
            return False, "데이터 없음"

        today = daily_data[0]
        open_price = today['open']
        close_price = today['close']
        high_price = today['high']
        low_price = today['low']

        # 양봉 확인 (종가 > 시가)
        if close_price <= open_price:
            return False, "음봉"

        # 몸통 비율 계산
        body = close_price - open_price
        total_range = high_price - low_price

        if total_range == 0:
            return False, "가격 변동 없음"

        body_ratio = body / total_range

        # 상승률 계산
        if open_price == 0:
            return False, "시가 0"

        change_ratio = (close_price - open_price) / open_price

        # 장대양봉 판단
        if body_ratio >= min_body_ratio and change_ratio >= min_change_ratio:
            return True, f"장대양봉 (몸통비율 {body_ratio*100:.1f}%, 상승률 {change_ratio*100:.1f}%)"
        else:
            return False, f"기준 미달 (몸통비율 {body_ratio*100:.1f}%, 상승률 {change_ratio*100:.1f}%)"

    except Exception as e:
        return False, f"오류: {str(e)}"


def filter_by_program_top50(kiwoom, code_list):
    """
    프로그램 순매수 상위 종목에 포함되는 종목만 필터링 (코스피 + 코스닥 통합)

    Args:
        kiwoom: Kiwoom API 인스턴스
        code_list: 필터링할 종목코드 리스트

    Returns:
        list: 프로그램 순매수 상위 종목에 포함되는 종목코드 리스트
    """
    try:
        # 프로그램 순매수 상위 종목 조회 (코스피 + 코스닥)
        top50_codes = get_program_top50_codes(kiwoom)

        if not top50_codes:
            print(f"[오류] 프로그램 순매수 상위 종목 조회 실패")
            return []

        # 입력 종목 중 상위 종목에 포함된 종목만 필터링
        filtered_codes = [code for code in code_list if code in top50_codes]

        print(
            f"[프로그램 순매수 필터링] 입력: {len(code_list)}개, 상위 종목 포함: {len(filtered_codes)}개")

        return filtered_codes

    except Exception as e:
        print(f"[오류] 프로그램 순매수 필터링 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


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
