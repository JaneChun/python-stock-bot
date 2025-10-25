"""
Rate Limiter Utility

API 호출 시 Rate Limiting을 적용하기 위한 유틸리티 함수
"""
import time
from typing import Callable, TypeVar
import pythoncom

T = TypeVar('T')


def apply_rate_limit(callback: Callable[..., T], delay: float = 0.2) -> T:
    """
    콜백 함수를 실행한 후 지정된 시간만큼 대기합니다.
    대기 중에도 COM 메시지를 처리하여 실시간 데이터 수신을 유지합니다.

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

    # delay 시간 동안 PumpWaitingMessages() 호출
    iterations = int(delay / 0.01)  # 10ms 단위로 쪼갬

    for _ in range(iterations):
        pythoncom.PumpWaitingMessages()
        time.sleep(0.01)

    return result
