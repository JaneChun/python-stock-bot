"""
데이터 포맷팅 유틸리티 함수
UI 표시용 문자열 변환
"""


def format_price(price: int) -> str:
    """가격 포맷팅"""
    return f"{price:,}"


def format_amount(amount: float) -> str:
    """거래대금 포맷팅"""
    return f"{amount:.1f}억"


def format_ratio(ratio: float) -> str:
    """배수 포맷팅"""
    return f"{ratio:.1f}x"
