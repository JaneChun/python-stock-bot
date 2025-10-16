"""
Rate Limiter Utility

API 호출 시 Rate Limiting을 적용하기 위한 유틸리티 함수
"""
import time
from typing import Callable, TypeVar, Any

T = TypeVar('T')


def apply_rate_limit(callback: Callable[..., T], delay: float = 0.2) -> T:
    """
    콜백 함수를 실행한 후 지정된 시간만큼 대기합니다.

    Args:
        callback: 실행할 함수
        delay: 함수 실행 후 대기 시간 (초, 기본값: 0.2)

    Returns:
        콜백 함수의 반환값

    Example:
        result = apply_rate_limit(lambda: filter_by_trading_volume(kiwoom, code))
        # 또는
        result = apply_rate_limit(filter_by_trading_volume, 0.2)(kiwoom, code)
    """
    result = callback()
    time.sleep(delay)
    return result
