"""
종목 필터링 API
- 거래량 폭증
- 외국인/기관 순매수
- 장대양봉
- 전고점 돌파/신고가
"""
from datetime import datetime
from pykrx import stock
from .market_data import get_daily_data, get_investor_data, get_stock_info


def filter_by_trading_volume(kiwoom, code):
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
        today_close = today['close']
        today_open = today['open']

        # 매수세 확인 (양봉 여부)
        is_bullish = today_close > today_open

        if not is_bullish:
            return False, f"매도세 (종가 {today_close:,} <= 시가 {today_open:,})"

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
