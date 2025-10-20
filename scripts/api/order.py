"""
주문 관련 API
"""
from datetime import datetime


def buy_stock(kiwoom, account, code, price, quantity, log_widget=None):
    """
    주식 매수 주문

    Args:
        kiwoom: Kiwoom API 인스턴스
        account: 계좌번호
        code: 종목코드
        price: 주문가격
        quantity: 주문수량
        log_widget: 로그 출력 위젯 (선택)

    Returns:
        bool: 주문 성공 여부
    """
    try:
        # 종목명 조회
        data = kiwoom.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        name = data['종목명'][0] if data and '종목명' in data else code
        current_time = datetime.now().strftime("%H:%M:%S")

        # 지정가 매수 주문
        order_type = 1  # 1=신규매수, 2=신규매도, 3=매수취소, 4=매도취소, 5=매수정정, 6=매도정정
        hoga_gb = "00"  # "00"=지정가, "03"=시장가

        order_result = kiwoom.SendOrder(
            "매수주문",      # 주문명
            "0101",         # 화면번호
            account,        # 계좌번호
            order_type,     # 주문유형
            code,           # 종목코드
            quantity,       # 주문수량
            price,          # 주문가격
            hoga_gb,        # 거래구분
            ""              # 원주문번호: 신규주문에는 공백
        )

        success = order_result == 0
        message = f'[{current_time}] [매수 주문 {"성공" if success else "실패"}] [{code}] [{name}] [가격: {price:,}] [수량: {quantity}]'

        if not success:
            message += f' [에러코드: {order_result}]'

        if log_widget:
            log_widget.append(message)

        print(message)
        return success

    except Exception as e:
        current_time = datetime.now().strftime("%H:%M:%S")
        error_message = f'[{current_time}] [매수 오류] [{code}] {str(e)}'

        if log_widget:
            log_widget.append(error_message)

        print(error_message)
        return False


def sell_stock(kiwoom, account, code, quantity, price=0, log_widget=None):
    """
    주식 매도 주문

    Args:
        kiwoom: Kiwoom API 인스턴스
        account: 계좌번호
        code: 종목코드
        quantity: 주문수량
        price: 주문가격 (0이면 시장가)
        log_widget: 로그 출력 위젯 (선택)

    Returns:
        bool: 주문 성공 여부
    """
    try:
        # 종목명 조회
        data = kiwoom.block_request(
            "opt10001",
            종목코드=code,
            output="주식기본정보",
            next=0
        )

        name = data['종목명'][0] if data and '종목명' in data else code
        current_time = datetime.now().strftime("%H:%M:%S")

        # 매도 주문
        order_type = 2  # 1=신규매수, 2=신규매도
        hoga_gb = "03" if price == 0 else "00"  # "00"=지정가, "03"=시장가

        order_result = kiwoom.SendOrder(
            "매도주문",      # 주문명
            "0101",         # 화면번호
            account,        # 계좌번호
            order_type,     # 주문유형
            code,           # 종목코드
            quantity,       # 주문수량
            price,          # 주문가격: 시장가는 0
            hoga_gb,        # 거래구분
            ""              # 원주문번호
        )

        success = order_result == 0
        price_str = f'{price:,}' if price > 0 else '시장가'
        message = f'[{current_time}] [매도 주문 {"성공" if success else "실패"}] [{code}] [{name}] [가격: {price_str}] [수량: {quantity}]'

        if not success:
            message += f' [에러코드: {order_result}]'

        if log_widget:
            log_widget.append(message)

        print(message)
        return success

    except Exception as e:
        current_time = datetime.now().strftime("%H:%M:%S")
        error_message = f'[{current_time}] [매도 오류] [{code}] {str(e)}'

        if log_widget:
            log_widget.append(error_message)

        print(error_message)
        return False


def sell_all_stocks(kiwoom, account, log_widget=None):
    """
    보유 종목 전체 매도

    Args:
        kiwoom: Kiwoom API 인스턴스
        account: 계좌번호
        log_widget: 로그 출력 위젯 (선택)

    Returns:
        int: 매도 주문한 종목 수
    """
    try:
        current_time = datetime.now().strftime("%H:%M:%S")
        message = f'[{current_time}] 보유 종목 전체 매도를 시작합니다.'

        if log_widget:
            log_widget.append(message)

        print(message)

        # 보유 종목 조회
        holdings = kiwoom.block_request(
            "opw00018",
            계좌번호=account,
            비밀번호="",
            비밀번호입력매체구분="00",
            조회구분="2",
            output="계좌평가잔고개별합산",
            next=0
        )

        if '종목번호' not in holdings or len(holdings['종목번호']) == 0:
            current_time = datetime.now().strftime("%H:%M:%S")
            message = f'[{current_time}] 보유 종목이 없습니다.'

            if log_widget:
                log_widget.append(message)

            print(message)
            return 0

        # 각 보유 종목에 대해 매도 주문 실행
        sell_count = 0
        for idx, code in enumerate(holdings['종목번호']):
            code = code.strip()[1:]  # 종목번호 앞에 붙는 'A' 제거
            quantity = int(holdings['보유수량'][idx])

            if quantity > 0:
                if sell_stock(kiwoom, account, code, quantity, 0, log_widget):
                    sell_count += 1

        current_time = datetime.now().strftime("%H:%M:%S")
        message = f'[{current_time}] 총 {sell_count}개 종목 매도 주문 완료'

        if log_widget:
            log_widget.append(message)

        print(message)
        return sell_count

    except Exception as e:
        current_time = datetime.now().strftime("%H:%M:%S")
        error_message = f'[{current_time}] [전체 매도 오류] {str(e)}'

        if log_widget:
            log_widget.append(error_message)

        print(error_message)
        return 0
