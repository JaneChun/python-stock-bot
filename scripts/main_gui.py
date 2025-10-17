"""
주식 자동 스크리닝 시스템 메인 GUI
매분마다 필터링된 종목을 자동으로 스캔하여 표시
"""

import os
import sys
import time
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import QTimer, Qt
from PyQt5 import uic
from dotenv import load_dotenv
from pykiwoom.kiwoom import Kiwoom

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.api.utils import apply_rate_limit  # noqa: E402
from scripts.api.filters import (
    filter_by_program,
    filter_by_volume_and_change
)  # noqa: E402
from scripts.api.screening import screen_by_custom_condition  # noqa: E402
from scripts.api.market_data import get_stock_info  # noqa: E402


# 환경변수 로드
load_dotenv()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # UI 파일 로드
        ui_path = os.path.join(os.path.dirname(__file__), 'gui.ui')
        uic.loadUi(ui_path, self)

        # Kiwoom API 초기화
        self.kiwoom = None
        self.account = None
        self.conditions = []  # 조건식 리스트

        # 타이머 설정
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.run_scan)  # 60초마다 스캔

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(
            self.update_countdown)  # 1초마다 countdown_remaining 값 업데이트
        self.countdown_remaining = 0

        # 스캔 중지 플래그
        self.stop_requested = False

        # 버튼 연결
        self.start_button.clicked.connect(self.start_auto_scan)
        self.stop_button.clicked.connect(self.stop_auto_scan)

        # 테이블 설정
        self.setup_table()

        # Kiwoom API 연결
        self.connect_kiwoom()

    def setup_table(self):
        """테이블 초기 설정"""
        # 헤더 크기 조정
        header = self.stock_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 종목코드
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 종목명
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 현재가
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 등락률
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 전일대비
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 거래량
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 선정시간

    def connect_kiwoom(self):
        """Kiwoom API 연결"""
        try:
            self.log("Kiwoom API 연결 중...")
            self.kiwoom = Kiwoom()
            self.kiwoom.CommConnect(block=True)

            # 계좌번호 가져오기
            self.account = self.kiwoom.GetLoginInfo("ACCNO")[0]

            if self.account:
                self.account_info.setText(self.account)
                self.connection_status.setText("연결됨")
                self.connection_status.setStyleSheet(
                    "color: green; font-weight: bold;")
                self.log(f"Kiwoom API 연결 성공 (계좌: {self.account})")

                # 조건식 리스트 로드
                self.load_conditions()
            else:
                raise Exception("계좌번호를 가져올 수 없습니다.")

        except Exception as e:
            self.log(f"Kiwoom API 연결 실패: {str(e)}")
            self.connection_status.setText("연결 실패")
            self.connection_status.setStyleSheet(
                "color: red; font-weight: bold;")

    def log(self, message):
        """로그 출력"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_browser.append(f"[{timestamp}] {message}")
        QApplication.processEvents()  # 로그 출력 시마다 GUI 자동 업데이트

    def load_conditions(self):
        """조건식 리스트 로드"""
        try:
            self.log("조건식 리스트 로드 중...")

            # 조건식을 PC로부터 다운로드
            self.kiwoom.GetConditionLoad()

            # 전체 조건식 리스트 얻기
            self.conditions = self.kiwoom.GetConditionNameList()

            if self.conditions:
                self.log(f"조건식 {len(self.conditions)}개 로드 완료")

                # ComboBox 초기화 및 조건식 추가
                self.condition_combobox.clear()
                for idx, (condition_index, condition_name) in enumerate(self.conditions):
                    self.condition_combobox.addItem(f"{idx}: {condition_name}")
            else:
                self.condition_combobox.addItem("조건식 없음")

        except Exception as e:
            self.log(f"조건식 로드 실패: {str(e)}")
            self.condition_combobox.addItem("조건식 로드 실패")

    def start_auto_scan(self):
        """자동 스캔 시작 (매분마다)"""
        if not self.kiwoom:
            self.log("Kiwoom API가 연결되지 않았습니다.")
            return

        self.log("자동 스캔 시작")

        # 중지 플래그 초기화
        self.stop_requested = False

        # 버튼 상태 변경
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        # 카운트다운 시작 (스캔 전에 먼저 시작)
        self.countdown_remaining = 60
        self.countdown_timer.start(1000)  # 1초마다 업데이트
        self.update_countdown()  # 즉시 표시 업데이트

        # 60초마다 스캔 실행 타이머 시작
        self.scan_timer.start(60000)  # 60초 = 60000ms

        # 즉시 첫 스캔 실행
        self.run_scan()

    def stop_auto_scan(self):
        """자동 스캔 중지"""
        # 중지 요청 플래그 설정
        self.stop_requested = True

        self.scan_timer.stop()
        self.countdown_timer.stop()

        # 버튼 상태 변경
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        self.next_scan_time.setText("--:--")
        self.log("자동 스캔 중지")

    def update_countdown(self):
        """다음 스캔까지 카운트다운 업데이트"""
        self.countdown_remaining -= 1

        if self.countdown_remaining <= 0:
            self.countdown_remaining = 60

        minutes = self.countdown_remaining // 60
        seconds = self.countdown_remaining % 60
        self.next_scan_time.setText(f"{minutes:02d}:{seconds:02d}")

    def should_stop(self):
        """중지 요청 확인 및 로그 출력"""
        if self.stop_requested:
            self.log("스캔 중지됨")
            return True
        return False

    def get_filter_parameters(self):
        """GUI에서 필터링 파라미터 값 읽기"""
        return {
            'condition_index': self.condition_combobox.currentIndex(),
            'program_count': self.program_count.value(),
            'ma_period': self.ma_period.value(),
            'volume_multiplier': self.volume_multiplier.value(),
            'min_change_ratio': self.min_change_ratio.value() / 100.0  # %를 비율로 변환
        }

    def run_scan(self):
        """스캔 실행 (스레드 없이 직접 실행)"""
        if not self.kiwoom:
            self.log("Kiwoom API가 연결되지 않았습니다.")
            return

        # 카운트다운 리셋
        self.countdown_remaining = 60

        try:
            self.log("=" * 60)
            self.log("스캔 시작...")

            # 필터 파라미터 읽기
            params = self.get_filter_parameters()
            condition_index = params['condition_index']
            condition_name = self.conditions[condition_index][1]
            self.log(f"설정: 조건검색[{condition_name}] 프로그램순매수[상위{params['program_count']}개] "
                     f"거래량[MA{params['ma_period']}의 {params['volume_multiplier']}배] 상승률[{params['min_change_ratio']*100:.1f}%]")

            if self.should_stop():
                return

            # 1단계: 초기 스크리닝 (조건검색)
            self.log(f"1단계: 조건검색 {params['condition_index']}번 종목 스크리닝...")
            codes, _ = screen_by_custom_condition(
                self.kiwoom, params['condition_index'])
            initial_count = len(codes)
            self.log(f"  ✔ {initial_count}개")
            self.update_statistics({
                'initial_count': initial_count,
                'program_count': 0,
                'volume_count': 0,
                'final_count': 0
            })

            if self.should_stop():
                return

            # 2단계: 프로그램 순매수 상위 N개 필터
            self.log(f"2단계: 프로그램 순매수 상위 {params['program_count']}개 조건 필터링...")
            filtered_codes = filter_by_program(
                self.kiwoom, codes, params['program_count'])
            program_count = len(filtered_codes)
            self.log(f"  ✔ {program_count}개")
            self.update_statistics({
                'initial_count': initial_count,
                'program_count': program_count,
                'volume_count': 0,
                'final_count': 0
            })

            if self.should_stop():
                return

            # 3단계: 거래량 + 상승률 필터
            self.log(f"3단계: 거래량(MA{params['ma_period']} x {params['volume_multiplier']}배) "
                     f"+ 상승률({params['min_change_ratio']*100:.1f}%) 필터링...")
            filtered_by_volume = filter_by_volume_and_change(
                self.kiwoom,
                filtered_codes,
                ma_period=params['ma_period'],
                volume_multiplier=params['volume_multiplier'],
                min_change_ratio=params['min_change_ratio']
            )

            volume_count = len(filtered_by_volume)
            self.log(f"  ✔ {volume_count}개")
            self.update_statistics({
                'initial_count': initial_count,
                'program_count': program_count,
                'volume_count': volume_count,
                'final_count': volume_count  # 최종 단계
            })

            if self.should_stop():
                return

            # 최종 결과 생성 (종목 상세 정보 포함)
            self.log(f"최종 종목 {volume_count}개 정보 조회중...")
            result_stocks = []

            for code in filtered_by_volume:
                if self.should_stop():
                    return

                try:
                    stock_info = apply_rate_limit(
                        lambda c=code: get_stock_info(self.kiwoom, c)
                    )

                    if stock_info:
                        result_stocks.append({
                            'code': stock_info['code'],
                            'name': stock_info['name'],
                            'price': stock_info['current_price'],
                            'change_rate': stock_info['change_rate'],
                            'price_change': stock_info['price_change'],
                            'volume': stock_info['volume'],
                            'time': datetime.now().strftime('%H:%M:%S')
                        })
                    else:
                        self.log(f"  ✗ {code} 정보 조회 실패")
                        # 기본 정보만 추가
                        result_stocks.append({
                            'code': code,
                            'name': self.kiwoom.GetMasterCodeName(code),
                            'price': 0,
                            'change_rate': 0.0,
                            'price_change': 0,
                            'volume': 0,
                            'time': datetime.now().strftime('%H:%M:%S')
                        })

                except Exception as e:
                    self.log(f"  ✗ {code} 정보 조회 실패: {str(e)}")
                    # 기본 정보만 추가
                    result_stocks.append({
                        'code': code,
                        'name': self.kiwoom.GetMasterCodeName(code),
                        'price': 0,
                        'change_rate': 0.0,
                        'price_change': 0,
                        'volume': 0,
                        'time': datetime.now().strftime('%H:%M:%S')
                    })

            # 결과 표시
            self.update_table(result_stocks)

            self.log(f"스캔 완료!")
            self.log("=" * 60)

        except Exception as e:
            self.log(f"ERROR: 스캔 중 오류 발생: {str(e)}")

    def update_statistics(self, stats):
        """통계 업데이트"""
        self.stat_initial_count.setText(str(stats['initial_count']))
        self.stat_program_count.setText(str(stats['program_count']))
        self.stat_volume_count.setText(str(stats['volume_count']))
        self.stat_final_count.setText(str(stats['final_count']))

    def update_table(self, stocks):
        """테이블 업데이트"""
        # 기존 데이터 클리어
        self.stock_table.setRowCount(0)

        # 새 데이터 추가
        for stock in stocks:
            row_position = self.stock_table.rowCount()
            self.stock_table.insertRow(row_position)

            # 종목코드
            self.stock_table.setItem(
                row_position, 0, QTableWidgetItem(stock['code']))

            # 종목명
            self.stock_table.setItem(
                row_position, 1, QTableWidgetItem(stock['name']))

            # 현재가
            price_item = QTableWidgetItem(f"{stock['price']:,}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stock_table.setItem(row_position, 2, price_item)

            # 등락률
            change_rate = stock['change_rate']
            change_item = QTableWidgetItem(f"{change_rate:+.2f}%")
            change_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if change_rate > 0:
                change_item.setForeground(Qt.red)
            elif change_rate < 0:
                change_item.setForeground(Qt.blue)
            self.stock_table.setItem(row_position, 3, change_item)

            # 전일대비
            price_change = stock['price_change']
            price_change_item = QTableWidgetItem(f"{price_change:+,}")
            price_change_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if price_change > 0:
                price_change_item.setForeground(Qt.red)
            elif price_change < 0:
                price_change_item.setForeground(Qt.blue)
            self.stock_table.setItem(row_position, 4, price_change_item)

            # 거래량
            volume_item = QTableWidgetItem(f"{stock['volume']:,}")
            volume_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stock_table.setItem(row_position, 5, volume_item)

            # 선정시간
            self.stock_table.setItem(
                row_position, 6, QTableWidgetItem(stock['time']))

        # 마지막 업데이트 시간
        self.last_update_time.setText(datetime.now().strftime('%H:%M:%S'))


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
