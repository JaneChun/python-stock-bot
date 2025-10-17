"""
종목 스크리닝 API (시가총액, 거래대금 기준, 프로그램 매매)
"""
from datetime import datetime
from .utils import safe_int, safe_float
from .utils.rate_limiter import apply_rate_limit


def screen_by_volume_and_market_cap(kiwoom):
    """
    거래대금 상위 종목 중 시가총액 필터링 스크리닝

    HTS 실시간 조건검색에서 만든 조건식을 사용하여:
    - 거래대금 상위 100개 기업 조회 (ETF, ETN, 관리종목 제외)
    - 시가총액 3천억 이상인 기업만 필터링

    Args:
        kiwoom: Kiwoom API 인스턴스

    Returns:
        list: 조건을 만족하는 종목 코드 리스트
    """
    try:
        # 조건식을 PC로부터 다운로드
        kiwoom.GetConditionLoad()

        # 전체 조건식 리스트 얻기
        conditions = kiwoom.GetConditionNameList()

        # 0번 조건식에 해당하는 종목 리스트 조회
        condition_index = conditions[0][0]
        condition_name = conditions[0][1]

        print(f"[스크리닝] 거래대금·시가총액 조건 종목 조회 중... (조건식: {condition_name})")

        codes = kiwoom.SendCondition(
            '0156',           # 화면번호 (요청 구분용 고유 식별자)
            condition_name,   # 조건식 이름
            condition_index,  # 조건식 고유번호
            0                 # 실시간옵션 (0:조건검색만, 1:조건검색+실시간)
        )

        # 조회 결과 처리
        if not codes:
            print("[스크리닝] 조회된 데이터가 없습니다.")
            return []

        print(f"[스크리닝] {len(codes)}개 종목 조회됨")

        return codes

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


def get_program_top50_codes(kiwoom):
    """
    프로그램 매매 순매수 상위 종목 코드 조회 (코스피 + 코스닥 통합)

    Args:
        kiwoom: Kiwoom API 인스턴스

    Returns:
        list: 프로그램 순매수 상위 종목 코드 리스트 (중복 제거)
    """
    try:
        all_data = []
        target_count = 60  # 조회할 종목 수

        # 코스피와 코스닥 모두 조회
        for market_code, market_name in [("P00101", "코스피"), ("P10102", "코스닥")]:
            print(
                f"[스크리닝] 프로그램 순매수 상위 50 종목 조회 중... (시장: {market_name})")

            market_data = []

            # 연속 조회로 45개 종목 수집 (15 * 3회 요청)
            for request_count in range(3):
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

        # 상위 50개만 선택
        top_50_data = unique_data[:50]

        top_50_codes = [item['code'] for item in top_50_data]

        print(f"[스크리닝] 프로그램 순매수 상위 {len(top_50_codes)}개 종목 조회됨")

        return top_50_codes

    except Exception as e:
        print(f"[오류] 프로그램 매매 순매수 상위 종목 조회 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
