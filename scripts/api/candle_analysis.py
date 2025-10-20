"""
캔들 분석 로직
함수형 프로그래밍 원칙을 적용한 순수 함수들
"""
from typing import List, Tuple, Optional, Dict
from .models import CandleData


def get_trading_amount(candle: CandleData) -> float:
    """거래대금 계산 (억원 단위)"""
    avg_price = (candle.open + candle.high + candle.low + candle.close) / 4
    return candle.volume * avg_price / 100000000


def is_amount_above_threshold(candle: CandleData, threshold_billion: float) -> bool:
    """
    캔들의 거래대금이 임계값 이상인지 체크

    Args:
        candle: 캔들 데이터
        threshold_billion: 임계값 (억원 단위)

    Returns:
        bool: 거래대금이 임계값 이상이면 True
    """
    amount = get_trading_amount(candle)
    return amount >= threshold_billion


def is_bullish_candle(candle: CandleData) -> bool:
    """양봉 체크"""
    return candle.close > candle.open


def check_body_tail_ratio(candle: CandleData, min_ratio: float) -> bool:
    """몸통이 윗꼬리보다 min_ratio배 이상인지 체크"""
    body = candle.close - candle.open
    upper_tail = candle.high - candle.close
    return body > upper_tail * min_ratio


def calculate_prev_avg_amount(prev_candles: List[Tuple[str, Dict]], lookback: int) -> float:
    """이전 N개 분봉의 평균 거래대금 계산"""
    if len(prev_candles) < lookback:
        return 0.0

    amounts = [
        get_trading_amount(CandleData(**data))
        for _, data in prev_candles[-lookback:]
    ]
    return sum(amounts) / len(amounts) if amounts else 0.0


def should_alert(
    candle: CandleData,
    prev_candles: List[Tuple[str, Dict]],
    min_amount: float,
    lookback: int,
    amount_multiplier: float,
    body_tail_ratio: float
) -> Tuple[bool, Optional[Tuple[float, float, float]]]:
    """
    알림 조건 체크 (순수 함수)

    Returns:
        (should_alert, (current_amount, avg_prev_amount, ratio) or None)
    """
    # 조건 1: 양봉 체크
    if not is_bullish_candle(candle):
        return False, None

    # 조건 2: 몸통/윗꼬리 비율 체크
    if not check_body_tail_ratio(candle, body_tail_ratio):
        return False, None

    # 조건 3: 거래대금 계산 (억원 단위)
    current_amount = get_trading_amount(candle)

    # 조건 4: 최소 거래대금 체크
    if current_amount < min_amount:
        return False, None

    # 조건 5: 이전 분봉들과 비교
    if len(prev_candles) < lookback:
        return False, None

    avg_prev_amount = calculate_prev_avg_amount(prev_candles, lookback)

    # 조건 6: 거래대금 배수 체크
    if avg_prev_amount <= 0 or current_amount < avg_prev_amount * amount_multiplier:
        return False, None

    ratio = current_amount / avg_prev_amount
    return True, (current_amount, avg_prev_amount, ratio)
