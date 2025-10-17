"""
종목 스크리닝 API (시가총액, 거래대금 기준, 프로그램 매매)
"""

import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .utils.rate_limiter import apply_rate_limit  # noqa: E402
from .utils import safe_int  # noqa: E402

from scripts.api.market_data import print_names  # noqa: E402


def screen_by_custom_condition(kiwoom, index=0):
    """
    HTS 조건검색식을 사용한 종목 스크리닝

    HTS 실시간 조건검색에서 만든 조건식을 인덱스로 선택하여 종목을 조회합니다.
    다양한 조건식을 사용할 수 있으며, index 파라미터로 원하는 조건을 선택할 수 있습니다.

    Args:
        kiwoom: Kiwoom API 인스턴스
        index: 조건식 인덱스 (기본값: 0)

    Returns:
        tuple: (종목 코드 리스트, 조건식 이름)
            - codes (list): 조건을 만족하는 종목 코드 리스트
            - condition_name (str): 사용된 조건식 이름
    """
    try:
        # 조건식을 PC로부터 다운로드
        kiwoom.GetConditionLoad()

        # 전체 조건식 리스트 얻기
        conditions = kiwoom.GetConditionNameList()

        # index번 조건식에 해당하는 종목 리스트 조회
        condition_index, condition_name = conditions[index]

        print(f"[스크리닝] (조건식: {condition_name}) 조건 종목 조회 중...")

        codes = kiwoom.SendCondition(
            '0150',           # 화면번호 (요청 구분용 고유 식별자)
            condition_name,   # 조건식 이름
            condition_index,  # 조건식 고유번호
            0                 # 실시간옵션 (0:조건검색만, 1:조건검색+실시간)
        )

        # 조회 결과 처리
        if not codes:
            print("[스크리닝] 조회된 데이터가 없습니다.")
            return ([], '')

        print(f"[스크리닝] {len(codes)}개 종목 조회됨")

        return (codes, condition_name)

    except Exception as e:
        print(f"[오류] 조건검색 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def screen_by_volume(kiwoom):
    """
    거래대금 상위 종목 스크리닝

    Args:
        kiwoom: Kiwoom API 인스턴스

    Returns:
        list: 종목 코드 리스트
    """
    try:
        print(f"[스크리닝] 거래대금 상위 종목 조회 중...")

        # OPT10032: 거래대금상위요청
        data = kiwoom.block_request(
            "opt10032",
            시장구분="000",            # 000:전체, 001:코스피, 101:코스닥
            관리종목포함="16",          # 0:미포함, 1:포함, 16:ETF+ETN제외
            거래소구분="",              # 공백: KRX
            output="거래대금상위",
            next=0
        )

        # DataFrame 처리
        if data is None or data.empty:
            print("[스크리닝] 조회된 데이터가 없습니다.")
            return []

        # ETF 제외
        etf = kiwoom.GetCodeListByMarket('8')

        codes = []
        for i in range(len(data)):
            code = data['종목코드'].iloc[i].strip()
            if code in etf:
                continue

            codes.append(code)

        print(f"[스크리닝] {len(codes)}개 종목 조회됨")

        return codes

    except Exception as e:
        print(f"[오류] 스크리닝 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def screen_by_program(kiwoom, count):
    """
    프로그램 매매 순매수 상위 종목 코드 조회 (코스피 + 코스닥 통합)

    Args:
        kiwoom: Kiwoom API 인스턴스
        count: 조회할 종목 수

    Returns:
        list: 프로그램 순매수 상위 종목 코드 리스트 (중복 제거)
    """
    try:
        all_data = []
        target_count = count

        # 코스피와 코스닥 모두 조회
        for market_code, market_name in [("P00101", "코스피"), ("P10102", "코스닥")]:
            print(
                f"[스크리닝] 프로그램 순매수 상위 종목 조회 중... (시장: {market_name}, 목표: {target_count}개)")

            market_data = []
            request_count = 0

            # target_count를 채울 때까지 반복 조회
            while len(market_data) < target_count:
                next_value = 0 if request_count == 0 else 2

                # OPT90003: 프로그램순매수상위50요청
                df = apply_rate_limit(lambda: kiwoom.block_request(
                    "opt90003",
                    매매상위구분="2",             # 1:순매도상위, 2:순매수상위
                    금액수량구분="1",             # 1:금액, 2:수량
                    시장구분=market_code,         # P00101:코스피, P10102:코스닥
                    거래소구분="1",               # 1:KRX, 2:NXT, 3:통합
                    output="프로그램순매수상위50",
                    next=next_value             # 첫 번째 요청: 0, 두 번째 요청부터: 2
                ), delay=0.5)

                # DataFrame 처리
                if df is None or df.empty:
                    print(
                        f"[스크리닝] {market_name} {request_count + 1}차 요청 데이터 없음 (조회 종료)")
                    break

                # 종목코드 컬럼이 있는지 확인
                if '종목코드' not in df.columns:
                    print(
                        f"[오류] {market_name} 종목코드 컬럼 없음. 사용 가능한 컬럼: {df.columns.tolist()}")
                    break

                # 데이터 추출
                for i in range(len(df)):
                    if len(market_data) >= target_count:
                        break

                    code = str(df['종목코드'].iloc[i]).strip()
                    program_net_buy_amount = safe_int(
                        df['프로그램순매수금액'].iloc[i]) if '프로그램순매수금액' in df.columns else None

                    if program_net_buy_amount is None:
                        print(f"[프로그램순매수금액] {code} 데이터 변환 실패로 스킵")
                        continue

                    market_data.append({
                        'code': code,
                        'program_net_buy_amount': program_net_buy_amount
                    })

                request_count += 1

            all_data.extend(market_data)

        # 중복 제거
        unique_data = []
        seen = set()
        for item in all_data:
            if item['code'] not in seen:
                unique_data.append(item)
                seen.add(item['code'])

        # 내림차순 정렬
        unique_data.sort(key=lambda x: -x['program_net_buy_amount'])

        result_codes = [item['code'] for item in unique_data]

        print(f"[스크리닝] 프로그램 순매수 상위 {len(result_codes)}개 종목 조회됨")
        # print_names(kiwoom, code_list=result_codes)

        return result_codes

    except Exception as e:
        print(f"[오류] 프로그램 매매 순매수 상위 종목 조회 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
