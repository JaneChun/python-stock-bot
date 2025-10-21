"""
데이터 변환 유틸리티 함수
"""


def safe_int(value, use_abs=False):
    """
    정수로 변환 (실패 시 None 반환)

    Args:
        value: 변환할 값
        use_abs: 절대값 사용 여부 (기본값: False)

    Returns:
        int | None: 변환된 정수값, 실패 시 None
    """
    try:
        # 문자열로 변환 후 콤마, + 기호 제거
        cleaned = str(value).replace(',', '').replace('+', '').strip()

        # use_abs=True일 때만 - 기호 제거
        if use_abs:
            cleaned = cleaned.replace('-', '')

        if not cleaned or cleaned == 'nan':
            return None

        result = int(cleaned)
        return abs(result) if use_abs else result

    except (ValueError, TypeError, AttributeError):
        return None


def safe_float(value):
    """
    실수로 변환 (실패 시 None 반환)

    Args:
        value: 변환할 값

    Returns:
        float | None: 변환된 실수값, 실패 시 None
    """
    try:
        # 문자열로 변환 후 콤마 제거
        cleaned = str(value).replace(',', '').strip()

        if not cleaned or cleaned == 'nan':
            return None

        return float(cleaned)

    except (ValueError, TypeError, AttributeError):
        return None
