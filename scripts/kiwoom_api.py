import os
from pykiwoom.kiwoom import Kiwoom
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 환경변수에서 비밀번호 가져오기
account_password = os.getenv("KIWOOM_ACCOUNT_PASSWORD")
if not account_password:
    raise ValueError("KIWOOM_ACCOUNT_PASSWORD 환경변수가 설정되지 않았습니다.")

kiwoom = Kiwoom()
kiwoom.CommConnect(block=True)  # 로그인

account_list = kiwoom.GetLoginInfo("ACCNO")  # 전체 계좌번호 리스트
account_number = account_list[0]

print(f"계좌번호: {account_number}")

# 예수금 조회
data = kiwoom.block_request("opw00001",
                            계좌번호=account_number,
                            비밀번호=account_password,
                            비밀번호입력매체구분="00",
                            조회구분=2,
                            output="예수금상세현황",
                            next=0)

deposit = data['예수금']
print(f"예수금: {deposit}원")

# 종목 조회
stock_codes = ['005930', '005380']

for code in stock_codes:
    data = kiwoom.block_request("opt10001",
                                종목코드=code,
                                output="주식기본정보",
                                next=0)
    name = data['종목명'][0]
    current_price = data['현재가'][0]  # 전일대비를 나타내는 +/-가 붙어있음
    print(f"{name}의 현재가: {current_price}원")
