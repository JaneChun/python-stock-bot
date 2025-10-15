"""
데이터 변환 유틸리티 함수
"""


class ConversionError(Exception):
    """데이터 변환 실패 예외"""
    pass


def safe_int(value, use_abs=False):
    """
    정수로 변환 (실패 시 예외 발생)

    Args:
        value: 변환할 값
        use_abs: 절대값 사용 여부 (기본값: False)

    Returns:
        int: 변환된 정수값

    Raises:
        ConversionError: 변환 실패 시 발생
    """
    try:
        # 문자열로 변환 후 콤마, +, - 기호 제거
        cleaned = str(value).replace(',', '').replace('+', '').replace('-', '').strip()

        if not cleaned or cleaned == 'nan':
            raise ConversionError(f"safe_int: 빈 값 또는 NaN 값 감지 (value={value})")

        result = int(cleaned)
        return abs(result) if use_abs else result

    except ConversionError:
        raise
    except (ValueError, TypeError, AttributeError) as e:
        raise ConversionError(f"safe_int: 정수 변환 실패 (value={value}, type={type(value).__name__}) - {str(e)}") from e


def safe_float(value):
    """
    실수로 변환 (실패 시 예외 발생)

    Args:
        value: 변환할 값

    Returns:
        float: 변환된 실수값

    Raises:
        ConversionError: 변환 실패 시 발생
    """
    try:
        # 문자열로 변환 후 콤마 제거
        cleaned = str(value).replace(',', '').strip()

        if not cleaned or cleaned == 'nan':
            raise ConversionError(f"safe_float: 빈 값 또는 NaN 값 감지 (value={value})")

        return float(cleaned)

    except ConversionError:
        raise
    except (ValueError, TypeError, AttributeError) as e:
        raise ConversionError(f"safe_float: 실수 변환 실패 (value={value}, type={type(value).__name__}) - {str(e)}") from e
