# pykiwoom 모듈 임포트
from pykiwoom.kiwoom import Kiwoom
import time

# 1. Kiwoom 객체 생성
kiwoom = Kiwoom()

# 2. 로그인
kiwoom.CommConnect(block=True)  # block=True: 로그인 완료될 때까지 대기

# 로그인 완료 후 계좌번호 가져오기
account_list = kiwoom.GetLoginInfo("ACCNO")  # 계좌번호 리스트 반환
account_number = account_list[0]  # 첫 번째 계좌 선택

# 3. 예수금 요청
# GetDeposit()는 특정 계좌의 예수금을 반환
deposit = kiwoom.GetDeposit(account_number)

# 4. 결과 출력
print(f"계좌번호: {account_number}")
print(f"예수금: {deposit}원")
