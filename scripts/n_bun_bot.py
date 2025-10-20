"""
실시간 거래대금 급증 탐지 GUI 시스템
함수형 프로그래밍 원칙을 적용하여 고성능 실시간 처리 구현
"""

import os
import sys
import time
import pythoncom
from datetime import datetime
from collections import deque
from typing import Dict, Tuple, Optional, List, Deque
from dataclasses import dataclass
import requests

from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt, QTimer
from PyQt5 import uic
from dotenv import load_dotenv
from pykiwoom.kiwoom import Kiwoom

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.api.utils import safe_int  # noqa: E402
from scripts.api.screening import screen_by_custom_condition  # noqa: E402

load_dotenv()

# ============================================================================
# 데이터 구조 (Immutable-like)
# ============================================================================


@dataclass(frozen=True)
class CandleData:
    """불변 캔들 데이터"""
    open: int
    high: int
    low: int
    close: int
    volume: int


@dataclass(frozen=True)
class AlertInfo:
    """불변 알림 정보"""
    time: str
    code: str
    name: str
    candle: CandleData
    current_amount: float
    avg_prev_amount: float
    ratio: float


# ============================================================================
# 순수 함수들 (Pure Functions)
# ============================================================================

def calculate_amount(candle: CandleData) -> float:
    """거래대금 계산 (억원 단위)"""
    avg_price = (candle.open + candle.high + candle.low + candle.close) / 4
    return candle.volume * avg_price / 100000000


def is_bullish_candle(candle: CandleData) -> bool:
    """양봉 체크"""
    return candle.close > candle.open


def check_body_tail_ratio(candle: CandleData, min_ratio: float) -> bool:
    """실체가 윗꼬리보다 min_ratio배 이상인지 체크"""
    body = candle.close - candle.open
    upper_tail = candle.high - candle.close
    return body > upper_tail * min_ratio


def calculate_prev_avg_amount(prev_candles: List[Tuple[str, Dict]], lookback: int) -> float:
    """이전 N개 분봉의 평균 거래대금 계산"""
    if len(prev_candles) < lookback:
        return 0.0

    amounts = [
        calculate_amount(CandleData(**data))
        for _, data in prev_candles[-lookback:]
    ]
    return sum(amounts) / len(amounts) if amounts else 0.0


def should_alert(
    candle: CandleData,
    prev_candles: List[Tuple[str, Dict]],
    min_amount: float,
    lookback: int,
    amount_multiplier: float,
    body_tail_ratio: float
) -> Tuple[bool, Optional[Tuple[float, float, float]]]:
    """
    알림 조건 체크 (순수 함수)

    Returns:
        (should_alert, (current_amount, avg_prev_amount, ratio) or None)
    """
    # 조건 1: 양봉 체크
    if not is_bullish_candle(candle):
        return False, None

    # 조건 2: 실체/윗꼬리 비율 체크
    if not check_body_tail_ratio(candle, body_tail_ratio):
        return False, None

    # 조건 3: 거래대금 계산
    current_amount = calculate_amount(candle)

    # 조건 4: 최소 거래대금 체크
    if current_amount < min_amount:
        return False, None

    # 조건 5: 이전 분봉들과 비교
    if len(prev_candles) < lookback:
        return False, None

    avg_prev_amount = calculate_prev_avg_amount(prev_candles, lookback)

    # 조건 6: 거래대금 배수 체크
    if avg_prev_amount <= 0 or current_amount < avg_prev_amount * amount_multiplier:
        return False, None

    ratio = current_amount / avg_prev_amount
    return True, (current_amount, avg_prev_amount, ratio)


def create_candle_chart(prev_candles: List[CandleData], current_candle: CandleData) -> str:
    """
    미니 캔들스틱 차트 생성 (ASCII)

    이전 3개 분봉 + 현재 분봉을 시각적으로 표현
    각 캔들의 강도(거래대금)도 함께 표현
    """
    all_candles = prev_candles + [current_candle]

    if not all_candles:
        return ""

    # 간단한 캔들 문자 표현 + 거래대금 크기 표현
    chart_symbols = []
    amounts = []

    for i, c in enumerate(all_candles):
        # 캔들 방향
        if c.close > c.open:
            # 양봉 - 실체 크기에 따라 다른 심볼
            body_ratio = (c.close - c.open) / c.open if c.open > 0 else 0
            if body_ratio > 0.05:  # 5% 이상 상승
                symbol = "🔥"
            elif body_ratio > 0.02:  # 2% 이상 상승
                symbol = "▲"
            else:
                symbol = "△"
        elif c.close < c.open:
            symbol = "▼"  # 음봉
        else:
            symbol = "─"  # 보합

        # 마지막 캔들 강조
        if i == len(all_candles) - 1:
            symbol = f"[{symbol}]"

        chart_symbols.append(symbol)

        # 거래대금
        amount = calculate_amount(c)
        amounts.append(amount)

    # 거래대금 증가 추세 표시
    trend = ""
    if len(amounts) >= 2:
        recent_trend = amounts[-1] / amounts[-2] if amounts[-2] > 0 else 1
        if recent_trend >= 3.0:
            trend = " 📈📈📈"
        elif recent_trend >= 2.0:
            trend = " 📈📈"
        elif recent_trend >= 1.5:
            trend = " 📈"

    return " ".join(chart_symbols) + trend


def format_price(price: int) -> str:
    """가격 포맷팅"""
    return f"{price:,}"


def format_amount(amount: float) -> str:
    """거래대금 포맷팅"""
    return f"{amount:.1f}억"


def format_ratio(ratio: float) -> str:
    """배수 포맷팅"""
    return f"{ratio:.1f}x"


# ============================================================================
# 메인 GUI 클래스
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # UI 파일 로드
        ui_path = os.path.join(os.path.dirname(
            __file__), 'volume_spike_gui.ui')
        uic.loadUi(ui_path, self)

        # Kiwoom API
        self.kiwoom: Optional[Kiwoom] = None
        self.account: Optional[str] = None
        self.conditions: List[Tuple[int, str]] = []

        # 실시간 데이터 저장소
        self.minute_data: Dict[str, Deque[Tuple[str, Dict]]] = {}
        self.ongoing_candles: Dict[str, Dict[str, Dict]] = {}
        self.alerted: Dict[str, str] = {}

        # 통계
        self.monitoring_codes: List[str] = []

        # Telegram Bot
        self.telegram_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None

        # UI 업데이트 최적화를 위한 버퍼
        self.pending_alerts: List[AlertInfo] = []
        self.last_ui_update = time.time()
        self.ui_update_interval = 0.1  # 100ms마다 UI 업데이트

        # pythoncom 메시지 처리를 위한 타이머
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self._pump_messages)
        self.message_timer.setInterval(10)  # 10ms마다 메시지 처리

        # 현재시간 업데이트 타이머
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self._update_current_time)
        self.time_timer.setInterval(1000)  # 1초마다 시간 업데이트
        # 시작 버튼 클릭 시에만 타이머 시작

        # 버튼 연결
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)

        # 테이블 설정
        self.setup_table()

        # Kiwoom API 연결
        self.connect_kiwoom()

        # Telegram Bot 연결
        self.connect_telegram()

    def setup_table(self):
        """테이블 초기 설정"""
        header = self.alert_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 시간
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 종목코드
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # 종목명
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 시가
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 고가
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 저가
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 종가
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 거래대금
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # 이전평균
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)  # 배수

    def connect_kiwoom(self):
        """Kiwoom API 연결"""
        try:
            self.log("Kiwoom API 연결 중...")
            self.kiwoom = Kiwoom()
            self.kiwoom.CommConnect(block=True)

            self.account = self.kiwoom.GetLoginInfo("ACCNO")[0]

            if self.account:
                self.account_info.setText(self.account)
                self.connection_status.setText("연결됨")
                self.connection_status.setStyleSheet(
                    "color: green; font-weight: bold;")
                self.log(f"✅️ Kiwoom API 연결 성공 (계좌: {self.account})")

                self.load_conditions()
            else:
                raise Exception("계좌번호를 가져올 수 없습니다.")

        except Exception as e:
            self.log(f"Kiwoom API 연결 실패: {str(e)}")
            self.connection_status.setText("연결 실패")
            self.connection_status.setStyleSheet(
                "color: red; font-weight: bold;")

    def load_conditions(self):
        """조건식 리스트 로드"""
        try:
            self.log("조건식 리스트 로드 중...")
            self.kiwoom.GetConditionLoad()
            self.conditions = self.kiwoom.GetConditionNameList()

            if self.conditions:
                self.log(f"✅️ 조건식 {len(self.conditions)}개 로드 완료")
                self.condition_combobox.clear()
                for idx, (condition_index, condition_name) in enumerate(self.conditions):
                    self.condition_combobox.addItem(f"{idx}: {condition_name}")
                # 기본값을 1번 인덱스로 설정
                if len(self.conditions) > 1:
                    self.condition_combobox.setCurrentIndex(1)
            else:
                self.condition_combobox.addItem("조건식 없음")

        except Exception as e:
            self.log(f"조건식 로드 실패: {str(e)}")
            self.condition_combobox.addItem("조건식 로드 실패")

    def connect_telegram(self):
        """Telegram Bot 연결"""
        try:
            token = os.getenv("TELEBOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")

            if not token:
                self.log("⚠️  Telegram Bot: TELEBOT_TOKEN이 설정되지 않았습니다.")
                return

            if not chat_id:
                self.log("⚠️  Telegram Bot: TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
                return

            self.telegram_token = token
            self.telegram_chat_id = chat_id

            # 연결 테스트
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                bot_info = response.json()
                bot_username = bot_info.get('result', {}).get('username', 'Unknown')
                self.log(f"✅ Telegram Bot 연결 성공: @{bot_username}")
            else:
                raise Exception(f"HTTP {response.status_code}")

        except Exception as e:
            self.log(f"❌ Telegram Bot 연결 실패: {str(e)}")
            self.telegram_token = None
            self.telegram_chat_id = None

    def send_telegram_message(self, alert: AlertInfo):
        """텔레그램 메시지 전송 (알림용)"""
        if not self.telegram_token or not self.telegram_chat_id:
            return

        try:
            # 메시지 포맷팅
            message = (
                f"🚨 *거래대금 급증 알림*\n\n"
                f"📈 *종목:* {alert.name}({alert.code})\n"
                f"⏰ *시간:* {alert.time}\n"
                f"💰 *현재가:* {format_price(alert.candle.close)}원\n"
                f"📊 *거래대금:* {format_amount(alert.current_amount)}\n"
                f"📉 *이전평균:* {format_amount(alert.avg_prev_amount)}\n"
                f"🔥 *급증배수:* {format_ratio(alert.ratio)}\n"
            )

            self._send_telegram(message)

        except Exception as e:
            self.log(f"❌ Telegram 메시지 전송 오류: {str(e)}")

    def send_telegram_start_message(self, condition_name: str, num_stocks: int, params: Dict):
        """텔레그램 시작 메시지 전송"""
        if not self.telegram_token or not self.telegram_chat_id:
            return

        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 메시지 포맷팅
            message = (
                f"✅ *모니터링 시작*\n\n"
                f"⏰ *시작 시간:* {current_time}\n"
                f"📋 *조건식:* {condition_name}\n"
                f"📊 *모니터링 종목:* {num_stocks}개\n\n"
                f"*탐지 조건:*\n"
                f"• 최소 거래대금: {params['min_amount']}억원\n"
                f"• 이전 분봉 개수: {params['lookback_candles']}개\n"
                f"• 급증 배수: {params['amount_multiplier']}배\n"
                f"• 실체/윗꼬리 비율: {params['body_tail_ratio']}배\n"
            )

            self._send_telegram(message)

        except Exception as e:
            self.log(f"❌ Telegram 시작 메시지 전송 오류: {str(e)}")

    def _send_telegram(self, message: str):
        """텔레그램 API 호출 (내부 메서드)"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }

            response = requests.post(url, json=data, timeout=5)

            if response.status_code != 200:
                error_msg = response.json().get('description', 'Unknown error')
                self.log(f"❌ Telegram 메시지 전송 실패: {error_msg}")

        except Exception as e:
            raise e

    def log(self, message: str):
        """로그 출력"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_browser.append(f"[{timestamp}] {message}")
        QApplication.processEvents()

    def get_parameters(self) -> Dict:
        """GUI에서 파라미터 읽기"""
        return {
            'condition_index': self.condition_combobox.currentIndex(),
            'min_amount': self.min_amount.value(),
            'lookback_candles': self.lookback_candles.value(),
            'amount_multiplier': self.amount_multiplier.value(),
            'body_tail_ratio': self.body_tail_ratio.value()
        }

    def start_monitoring(self):
        """실시간 모니터링 시작"""
        if not self.kiwoom:
            self.log("Kiwoom API가 연결되지 않았습니다.")
            return

        try:
            self.log("=" * 60)
            self.log("실시간 거래대금 급증 탐지 시작")

            params = self.get_parameters()
            condition_name = self.conditions[params['condition_index']][1]

            self.log(f"설정: 조건검색[{condition_name}] "
                     f"최소거래대금[{params['min_amount']}억원] "
                     f"이전분봉[{params['lookback_candles']}개] "
                     f"배수[{params['amount_multiplier']}배] "
                     f"실체/윗꼬리[{params['body_tail_ratio']}배]")

            # 조건 검색으로 종목 코드 리스트 불러오기
            codes, _ = screen_by_custom_condition(
                self.kiwoom, params['condition_index'])
            self.monitoring_codes = codes
            self.log(f"모니터링 대상 종목: {len(codes)}개")

            # 데이터 구조 초기화
            self.minute_data = {code: deque(
                maxlen=params['lookback_candles']) for code in codes}
            self.ongoing_candles = {}
            self.alerted = {}

            # 알림 테이블 초기화 (이전 알림 목록 삭제)
            self.alert_table.setRowCount(0)

            # SetRealReg로 실시간 조회 등록 (100개씩)
            for i in range(len(codes) // 100 + 1):
                subset = codes[i*100:(i+1)*100]
                reg_type = "0" if i == 0 else "1"
                if subset:
                    self.kiwoom.SetRealReg(
                        str(1000+i),
                        ";".join(subset),
                        "10;15;20",  # 10=현재가, 15=거래량, 20=체결시간
                        reg_type
                    )

            self.log(f"{len(codes)}개 종목 실시간 등록 완료")

            # 이벤트 핸들러 연결
            self.kiwoom.ocx.OnReceiveRealData.connect(
                self._on_receive_real_data)

            # UI 업데이트
            self.monitoring_count.setText(f"{len(codes)}개")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

            self.log("모니터링 시작됨")
            self.log("=" * 60)

            # 텔레그램 시작 메시지 전송
            self.send_telegram_start_message(condition_name, len(codes), params)

            # 메시지 처리 타이머 시작
            self.message_timer.start()

            # 현재시간 타이머 시작
            self.time_timer.start()

        except Exception as e:
            self.log(f"ERROR: 모니터링 시작 실패: {str(e)}")

    def stop_monitoring(self):
        """실시간 모니터링 중지"""
        try:
            # 타이머 중지
            self.message_timer.stop()
            self.time_timer.stop()

            # 현재시간 리셋
            self.current_time.setText("--:--:--")

            # 실시간 등록 해제
            if self.kiwoom:
                self.kiwoom.SetRealRemove('ALL', 'ALL')

            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.log("모니터링 중지됨")

        except Exception as e:
            self.log(f"ERROR: 모니터링 중지 실패: {str(e)}")

    def _pump_messages(self):
        """pythoncom 메시지 처리 (QTimer에서 주기적으로 호출)"""
        try:
            pythoncom.PumpWaitingMessages()
        except Exception as e:
            self.log(f"ERROR: 메시지 처리 오류: {str(e)}")

    def _update_current_time(self):
        """현재시간 업데이트 (1초마다 호출)"""
        current_time = datetime.now().strftime('%H:%M:%S')
        self.current_time.setText(current_time)

    def _on_receive_real_data(self, sCode: str, sRealType: str, sRealData: str):
        """
        실시간 데이터 수신 핸들러
        성능 최적화를 위해 최소한의 로직만 포함
        """
        try:
            if sRealType != "주식체결":
                return

            # 데이터 추출
            price = safe_int(self.kiwoom.GetCommRealData(
                sCode, 10), use_abs=True)
            volume = safe_int(self.kiwoom.GetCommRealData(
                sCode, 15), use_abs=True)
            current_minute = datetime.now().strftime("%H:%M")

            # 데이터 유효성 체크
            if price <= 0 or volume <= 0:
                return

            # 분봉 데이터 업데이트
            self._update_candle_data(sCode, current_minute, price, volume)

            # 알림 조건 체크
            self._check_and_alert(sCode, current_minute)

            # UI 업데이트 (throttling)
            self._flush_pending_alerts()

        except Exception as e:
            # 성능을 위해 로그 출력 최소화
            pass

    def _update_candle_data(self, code: str, current_minute: str, price: int, volume: int):
        """분봉 데이터 업데이트 (mutable 상태 관리)"""
        if code not in self.ongoing_candles:
            self.ongoing_candles[code] = {}

        # 새로운 분이 시작되면 이전 분 데이터를 확정 분봉으로 저장
        if current_minute not in self.ongoing_candles[code]:
            if self.ongoing_candles[code]:
                prev_minute = max(self.ongoing_candles[code].keys())
                prev_data = self.ongoing_candles[code][prev_minute]

                if code in self.minute_data:
                    self.minute_data[code].append((prev_minute, prev_data))

                del self.ongoing_candles[code][prev_minute]

                # 새로운 분이 시작되면 알림 기록 초기화
                if code in self.alerted:
                    del self.alerted[code]

            # 새 분 데이터 초기화
            self.ongoing_candles[code][current_minute] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume
            }
        else:
            # 같은 분 내에서 데이터 갱신
            d = self.ongoing_candles[code][current_minute]
            d["high"] = max(d["high"], price)
            d["low"] = min(d["low"], price)
            d["close"] = price
            d["volume"] += volume

    def _check_and_alert(self, code: str, current_minute: str):
        """알림 조건 체크 및 알림 생성"""
        # 이미 이번 분에 알림을 보냈으면 스킵
        if code in self.alerted and self.alerted[code] == current_minute:
            return

        # 현재 진행 중인 분봉 데이터 가져오기
        if code not in self.ongoing_candles or current_minute not in self.ongoing_candles[code]:
            return

        candle_dict = self.ongoing_candles[code][current_minute]
        candle = CandleData(**candle_dict)

        # 파라미터 가져오기
        params = self.get_parameters()

        # 알림 조건 체크 (순수 함수 사용)
        prev_candles = list(self.minute_data.get(code, []))
        result, data = should_alert(
            candle,
            prev_candles,
            params['min_amount'],
            params['lookback_candles'],
            params['amount_multiplier'],
            params['body_tail_ratio']
        )

        if result and data:
            current_amount, avg_prev_amount, ratio = data

            # 알림 정보 생성
            stock_name = self.kiwoom.GetMasterCodeName(code)
            alert = AlertInfo(
                time=datetime.now().strftime('%H:%M:%S'),
                code=code,
                name=stock_name,
                candle=candle,
                current_amount=current_amount,
                avg_prev_amount=avg_prev_amount,
                ratio=ratio
            )

            # 버퍼에 추가
            self.pending_alerts.append(alert)

            # 알림 기록
            self.alerted[code] = current_minute

            # 로그 출력
            self.log(f"🚨 거래대금 급증: {stock_name}({code}) "
                     f"{format_amount(current_amount)} (이전 평균 {format_amount(avg_prev_amount)}, "
                     f"{format_ratio(ratio)})")

            # 텔레그램 메시지 전송
            self.send_telegram_message(alert)

    def _flush_pending_alerts(self):
        """보류 중인 알림을 UI에 반영 (throttling)"""
        current_time = time.time()

        if current_time - self.last_ui_update < self.ui_update_interval:
            return

        if not self.pending_alerts:
            return

        # 모든 보류 중인 알림 처리
        for alert in self.pending_alerts:
            self._add_alert_to_table(alert)

        # 버퍼 클리어
        self.pending_alerts.clear()
        self.last_ui_update = current_time

    def _add_alert_to_table(self, alert: AlertInfo):
        """테이블에 알림 추가"""
        # 메모리 관리: 최대 1000개까지만 유지
        MAX_ROWS = 1000
        if self.alert_table.rowCount() >= MAX_ROWS:
            self.alert_table.removeRow(MAX_ROWS - 1)

        row_position = 0
        self.alert_table.insertRow(row_position)

        # 시간
        self.alert_table.setItem(row_position, 0, QTableWidgetItem(alert.time))

        # 종목코드
        self.alert_table.setItem(row_position, 1, QTableWidgetItem(alert.code))

        # 종목명
        self.alert_table.setItem(row_position, 2, QTableWidgetItem(alert.name))

        # 시가, 고가, 저가, 종가
        for idx, price in enumerate([alert.candle.open, alert.candle.high,
                                     alert.candle.low, alert.candle.close]):
            item = QTableWidgetItem(format_price(price))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.alert_table.setItem(row_position, 3 + idx, item)

        # 거래대금
        amount_item = QTableWidgetItem(format_amount(alert.current_amount))
        amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alert_table.setItem(row_position, 7, amount_item)

        # 이전평균
        avg_item = QTableWidgetItem(format_amount(alert.avg_prev_amount))
        avg_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.alert_table.setItem(row_position, 8, avg_item)

        # 배수
        ratio_item = QTableWidgetItem(format_ratio(alert.ratio))
        ratio_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ratio_item.setForeground(Qt.red)
        self.alert_table.setItem(row_position, 9, ratio_item)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
