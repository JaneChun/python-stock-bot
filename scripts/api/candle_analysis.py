"""
캔들 분석 로직
"""
from typing import List, Tuple, Dict
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
    # 부분 데이터를 건너뛰기 위해 lookback+1개 이상 필요
    if len(prev_candles) < lookback + 1:
        return 0.0

    amounts = [
        get_trading_amount(CandleData(**data))
        for _, data in prev_candles[-lookback:]
    ]
    return sum(amounts) / len(amounts) if amounts else 0.0
