"""
주식 데이터 모델
실시간 거래 분석에 사용되는 불변 데이터 구조
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CandleData:
    """불변 캔들 데이터"""
    open: int
    high: int
    low: int
    close: int
    volume: int


@dataclass(frozen=True)
class AlertInfo:
    """불변 알림 정보"""
    time: str
    code: str
    name: str
    candle: CandleData
    current_amount: float
    avg_prev_amount: float
    ratio: float
    program_rank: int
