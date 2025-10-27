"""
실시간 거래대금 급증 탐지 시스템
"""

import os
import sys
import time
import queue
import pythoncom
import traceback
import threading
from datetime import datetime
from collections import deque
from typing import Dict, Tuple, Optional, List, Deque

from dotenv import load_dotenv
from pykiwoom.kiwoom import Kiwoom

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.api.utils import safe_int  # noqa: E402
from scripts.api.screening import screen_by_custom_condition, screen_by_program  # noqa: E402
from scripts.api.models import CandleData, AlertInfo  # noqa: E402
from scripts.api.candle_analysis import (  # noqa: E402
    get_trading_amount,
    is_bullish_candle,
    check_body_tail_ratio,
    calculate_prev_avg_amount
)
from scripts.api.filters import check_ma_alignment, check_trader_sell_dominance  # noqa: E402
from scripts.api.utils.formatters import format_price, format_amount, format_ratio  # noqa: E402
from scripts.api.telegram_bot import TelegramBot  # noqa: E402

load_dotenv()


# ============================================================================
# 설정값
# ============================================================================
class Config:
    # 조건검색 설정
    CONDITION_INDEX = 1  # 사용할 조건검색식 인덱스

    # 필터링 조건
    MIN_AMOUNT = 10.0  # 최소 거래대금 (단위: 억원)
    LOOKBACK_CANDLES = 3  # 비교할 이전 분봉 개수
    AMOUNT_MULTIPLIER = 3.0  # 거래대금 증가 배수
    BODY_TAIL_RATIO = 1.2  # 몸통/윗꼬리 최소 비율
    PROGRAM_COUNT = 30  # 프로그램 순매수 상위 N개
    MA_TICK = 3  # 이동평균선 기준 분봉
    MA_PERIODS = [20, 40, 60]  # 이동평균선 기간 (짧은 순서)
    TRADER_CODE = "050"  # 거래원 설정 (키움증권=050)

    # 필터 활성화 여부
    ENABLE_MIN_AMOUNT = True
    ENABLE_LOOKBACK = True
    ENABLE_BODY_TAIL = True
    ENABLE_PROGRAM = True
    ENABLE_MA_ALIGNMENT = True
    ENABLE_TRADER_SELL = True  # 거래원 매도 우위 체크
    ENABLE_TELEGRAM = True

    # 시스템 설정
    PROGRAM_REFRESH_INTERVAL = 30  # 프로그램 순매수 갱신 주기 (초)
    THROTTLE_SECONDS = 10  # 동일 종목 재체크 방지 시간 (초)


# ============================================================================
# 알림 조건 체크 함수 (TR 조회 없음)
# ============================================================================
def should_alert(
    candle: CandleData,
    prev_candles: List[Tuple[str, Dict]],
    code: str,
    program_top_codes: List[str],
    config: Config
) -> Tuple[bool, Optional[Tuple[float, float, float, int]]]:
    """
    1단계 필터링: TR 조회 없이 빠른 조건 체크
    """
    # 1. 양봉 체크
    if not is_bullish_candle(candle):
        return False, None

    # 2. 몸통/윗꼬리 비율 체크
    if config.ENABLE_BODY_TAIL:
        if not check_body_tail_ratio(candle, config.BODY_TAIL_RATIO):
            return False, None

    current_amount = get_trading_amount(candle)

    # 3. 최소 거래대금 체크
    if config.ENABLE_MIN_AMOUNT:
        if current_amount < config.MIN_AMOUNT:
            return False, None

    # 4. 거래대금 급증 체크
    avg_prev_amount = 0
    ratio = 0
    if config.ENABLE_LOOKBACK:
        if len(prev_candles) < config.LOOKBACK_CANDLES:
            return False, None
        avg_prev_amount = calculate_prev_avg_amount(
            prev_candles, config.LOOKBACK_CANDLES)
        if avg_prev_amount <= 0:
            return False, None
        ratio = current_amount / avg_prev_amount
        if ratio < config.AMOUNT_MULTIPLIER:
            print(f"[DEBUG] {code}: ✔️✔️✔️")
            return False, None

    # 5. 프로그램 순매수 체크
    program_rank = 0
    if config.ENABLE_PROGRAM:
        if code not in program_top_codes:
            print(f"[DEBUG] {code}: ✔️✔️✔️✔️")
            return False, None
        program_rank = program_top_codes.index(code) + 1
        print(f"[DEBUG] {code}: ✔️✔️✔️✔️✔️")

    return True, (current_amount, avg_prev_amount, ratio, program_rank)


# ============================================================================
# 메인 로직 클래스
# ============================================================================
class NBunBot:
    def __init__(self, config: Config):
        self.config = config
        self.kiwoom: Optional[Kiwoom] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.conditions: List[Tuple[int, str]] = []

        # 실시간 데이터 저장소
        self.minute_data: Dict[str, Deque[Tuple[str, Dict]]] = {}
        self.ongoing_candles: Dict[str, Dict[str, Dict]] = {}
        self.alerted: Dict[str, str] = {}
        self.last_check_time: Dict[str, float] = {}

        # 캐시 및 상태
        self.monitoring_codes: List[str] = []
        self.program_top_codes: List[str] = []
        self.is_requesting = False  # TR 동시 조회 방지
        self.is_running = False
        self.program_refresh_timer: Optional[threading.Timer] = None
        self.request_queue = queue.Queue()  # 스레드 간 요청 큐

    def log(self, message: str):
        """콘솔에 로그 출력"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def _connect_kiwoom(self):
        """Kiwoom API 연결 및 초기화"""
        self.log("🔲 Kiwoom API 연결 시도...")
        self.kiwoom = Kiwoom()
        self.kiwoom.CommConnect(block=True)
        account = self.kiwoom.GetLoginInfo("ACCNO")[0]
        self.log(f"✅ Kiwoom API 연결 성공 (계좌: {account})")

        self.log("🔲 조건식 리스트 로드...")
        self.kiwoom.GetConditionLoad()
        self.conditions = self.kiwoom.GetConditionNameList()
        if not self.conditions:
            raise Exception("조건식을 찾을 수 없습니다.")
        self.log(f"✅ 조건식 {len(self.conditions)}개 로드 완료")

    def _connect_telegram(self):
        """텔레그램 봇 연결"""
        if not self.config.ENABLE_TELEGRAM:
            self.log("텔레그램 비활성화 상태입니다.")
            return

        token = os.getenv("TELEBOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            self.log("⚠️ 텔레그램 설정(TELEBOT_TOKEN, TELEGRAM_CHAT_ID)이 필요합니다.")
            return

        self.telegram_bot = TelegramBot(token, chat_id, logger=self.log)
        self.telegram_bot.connect()
        self.log(f"✅ 텔레그램 연결 완료")

    def start(self):
        """실시간 모니터링 시작"""
        try:
            self._connect_kiwoom()
            self._connect_telegram()
            self.is_running = True

            self.log("=" * 60)
            self.log("실시간 거래대금 급증 탐지 시작")

            # 1. 모니터링 대상 종목 선정
            condition_index = self.config.CONDITION_INDEX
            codes, _ = screen_by_custom_condition(self.kiwoom, condition_index)
            self.monitoring_codes = codes
            self.log(f"모니터링 대상 종목: {len(codes)}개")

            # 2. 데이터 구조 초기화
            self.minute_data = {code: deque(
                maxlen=self.config.LOOKBACK_CANDLES + 1) for code in codes}
            self.ongoing_candles = {}
            self.alerted = {}
            self.last_check_time = {}

            # 3. 실시간 시세 등록 (100개씩)
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
            self.log(f"{len(codes)}개 종목 실시간 데이터 수신 등록 완료")

            # 4. 이벤트 핸들러 연결
            self.kiwoom.ocx.OnReceiveRealData.connect(
                self._on_receive_real_data)

            # 5. 타이머 및 초기 데이터 로드
            if self.config.ENABLE_PROGRAM:
                self._execute_refresh_program_codes()  # 시작 시 즉시 실행
                # 주기적 실행을 위한 타이머 설정
                self.program_refresh_timer = threading.Timer(
                    self.config.PROGRAM_REFRESH_INTERVAL,
                    self._schedule_refresh_program_codes
                )
                self.program_refresh_timer.start()

            # 6. 텔레그램 시작 메시지 전송
            if self.telegram_bot:
                message = self._get_conditions_text()
                self.telegram_bot.send_start_message(message)

            self.log("=" * 60)
            self._run_loop()

        except Exception as e:
            self.log(f"❌ 시작 중 오류 발생: {e}")
            traceback.print_exc()

    def stop(self):
        """실시간 모니터링 중지"""
        if not self.is_running:
            return
        self.log("모니터링 중지 시작...")
        self.is_running = False

        if self.program_refresh_timer:
            self.program_refresh_timer.cancel()

        if self.kiwoom:
            self.kiwoom.SetRealRemove('ALL', 'ALL')
            self.log("실시간 데이터 수신 해제")

        if self.telegram_bot:
            self.telegram_bot.send_stop_message()

        self.log("✅ 모니터링이 중지되었습니다.")

    def _run_loop(self):
        """메인 이벤트 루프: COM 메시지 처리 및 요청 큐 확인"""
        self.log("메인 루프 시작. (Ctrl+C로 종료)")
        while self.is_running:
            # 1. 요청 큐에서 작업 확인 및 실행
            try:
                request_type, payload = self.request_queue.get_nowait()
                if request_type == "REFRESH_PROGRAM_CODES":
                    self._execute_refresh_program_codes()
                elif request_type == "CHECK_TR_FILTERS":
                    self._execute_tr_filters(payload)
            except queue.Empty:
                pass

            # 2. COM 메시지 처리
            pythoncom.PumpWaitingMessages()
            time.sleep(0.01)

    def _get_conditions_text(self) -> str:
        """텔레그램 메시지에 포함될 조건 텍스트 생성"""
        c = self.config
        condition_name = self.conditions[c.CONDITION_INDEX][1]
        conditions_text = f"📋 *조건식:* {condition_name}\n"
        conditions_text += f"📊 *모니터링 종목:* {len(self.monitoring_codes)}개\n\n"
        conditions_text += "*알림 조건:*\n"

        if c.ENABLE_MIN_AMOUNT:
            conditions_text += f"• 최소 거래대금: {c.MIN_AMOUNT}억원\n"
        if c.ENABLE_LOOKBACK:
            conditions_text += f"• 이전 분봉 개수: {c.LOOKBACK_CANDLES}개\n"
            conditions_text += f"• 급증 배수: {c.AMOUNT_MULTIPLIER}배\n"
        if c.ENABLE_BODY_TAIL:
            conditions_text += f"• 몸통/윗꼬리 비율: {c.BODY_TAIL_RATIO}배\n"
        if c.ENABLE_PROGRAM:
            conditions_text += f"• 프로그램 순매수 상위 [{c.PROGRAM_COUNT}]위 이내\n"
        if c.ENABLE_MA_ALIGNMENT:
            ma_periods_str = ' ≥ '.join(map(str, c.MA_PERIODS))
            conditions_text += f"• {c.MA_TICK}분봉 이동평균선 정배열: {ma_periods_str}\n"
        if c.ENABLE_TRADER_SELL:
            conditions_text += f"• 거래원 매도 우위: 키움증권({c.TRADER_CODE})"
        return conditions_text

    def _get_alert_text(self, alert: AlertInfo) -> str:
        """알림 메시지 텍스트 생성 (활성화된 필터 조건만 포함)"""
        c = self.config

        # 기본 정보
        message = f"🚀 *{alert.name}({alert.code})*\n\n"
        message += f"💰 *현재가*: {format_price(alert.candle.close)}원\n"
        message += f"⏰ *시간*: {alert.time}\n\n"

        # 활성화된 필터 조건에 따라 동적으로 추가
        details = []

        if c.ENABLE_LOOKBACK:
            details.append(f"💥 *급증 거래대금*: {format_ratio(alert.ratio)[:-1]}배")
            details.append(
                f"📊 *거래대금*: {format_amount(alert.current_amount)} (이전평균: {format_amount(alert.avg_prev_amount)})")
        elif c.ENABLE_MIN_AMOUNT:
            details.append(f"📊 *거래대금*: {format_amount(alert.current_amount)}")

        if c.ENABLE_PROGRAM and alert.program_rank > 0:
            details.append(f"🤖 *프로그램 순매수 순위*: {alert.program_rank}위")

        if c.ENABLE_MA_ALIGNMENT:
            ma_periods_str = ' ≥ '.join(map(str, c.MA_PERIODS))
            details.append(f"📈 *MA 정배열*: {ma_periods_str}")

        if c.ENABLE_TRADER_SELL:
            details.append(f"🔹 *거래원 매도 우위*: 키움증권({c.TRADER_CODE})")

        message += '\n'.join(details)

        return message

    def _schedule_refresh_program_codes(self):
        """(보조 스레드에서 실행) 메인 스레드에 프로그램 순매수 갱신을 요청"""
        if not self.is_running:
            return

        # 메인 스레드가 처리하도록 큐에 요청 추가
        self.request_queue.put(("REFRESH_PROGRAM_CODES", None))

        # 다음 타이머 설정
        if self.is_running:
            self.program_refresh_timer = threading.Timer(
                self.config.PROGRAM_REFRESH_INTERVAL,
                self._schedule_refresh_program_codes
            )
            self.program_refresh_timer.start()

    def _execute_refresh_program_codes(self):
        """(메인 스레드에서 실행) 실제 프로그램 순매수 데이터를 조회하고 갱신"""
        if self.is_requesting:
            self.log("[프로그램 순매수] 다른 TR 조회 진행 중 - 이번 갱신 스킵")
            return

        try:
            self.is_requesting = True
            codes = screen_by_program(self.kiwoom, self.config.PROGRAM_COUNT)
            if codes:
                self.program_top_codes = codes
                self.log(f"[프로그램 순매수] 상위 {len(codes)}개 종목 갱신 완료")
            else:
                self.log("[프로그램 순매수] 조회 실패 - 이전 데이터 유지")
        finally:
            self.is_requesting = False

    def _on_receive_real_data(self, sCode: str, sRealType: str, sRealData: str):
        """실시간 데이터 수신 핸들러"""
        if sRealType != "주식체결":
            return

        try:
            # 데이터 추출
            price = safe_int(self.kiwoom.GetCommRealData(
                sCode, 10), use_abs=True)
            volume = safe_int(self.kiwoom.GetCommRealData(
                sCode, 15), use_abs=True)
            exec_time_str = self.kiwoom.GetCommRealData(sCode, 20)  # "HHMMSS"
            current_minute = exec_time_str[:4]  # "HHMM"

            # 데이터 유효성 체크
            if price <= 0 or volume <= 0:
                return

            # 분봉 데이터 업데이트
            self._update_candle_data(sCode, current_minute, price, volume)

            # 알림 조건 체크
            self._check_and_alert(sCode, current_minute, exec_time_str)

        except Exception as e:
            self.log(f"❌ _on_receive_real_data 오류 ({sCode}): {e}")
            traceback.print_exc()

    def _update_candle_data(self, code: str, current_minute: str, price: int, volume: int):
        """분봉 데이터 업데이트"""
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

    def _check_and_alert(self, code: str, current_minute: str, exec_time_str: str):
        """알림 조건 체크 및 발송 요청"""

        # 1. 중복 알림, 체크 방지
        if code in self.alerted and self.alerted[code] == current_minute:
            return

        now = time.time()
        if now - self.last_check_time.get(code, 0) < self.config.THROTTLE_SECONDS:
            return
        self.last_check_time[code] = now

        # 2. 현재 분봉 데이터 가져오기
        if code not in self.ongoing_candles or current_minute not in self.ongoing_candles[code]:
            return
        candle = CandleData(**self.ongoing_candles[code][current_minute])

        # 3. 1단계 필터링 (빠른 필터)
        program_codes_snapshot = self.program_top_codes.copy()
        prev_candles = list(self.minute_data.get(code, []))
        result, data = should_alert(
            candle, prev_candles, code, program_codes_snapshot, self.config)

        if not result:
            return
        self.log(f"✅ {code} - 1단계 필터 통과")

        # 4. TR 필터 필요 여부 확인
        needs_tr_filters = self.config.ENABLE_MA_ALIGNMENT or self.config.ENABLE_TRADER_SELL
        if not needs_tr_filters:
            self._execute_final_alert(
                code, current_minute, candle, data, exec_time_str)
            return

        # 5. TR 필터링을 위해 큐에 작업 요청
        payload = {
            "code": code,
            "candle": candle,
            "data": data,
            "current_minute": current_minute,
            "exec_time_str": exec_time_str
        }
        self.request_queue.put(("CHECK_TR_FILTERS", payload))

    def _execute_tr_filters(self, payload: Dict):
        """(메인 스레드에서 실행) TR 조회가 필요한 필터들을 체크하고 최종 알림 발송"""
        code = payload['code']

        if self.is_requesting:
            self.log(f"[{code}] 다른 TR 조회 진행 중 - TR 필터 스킵")
            return

        try:
            self.is_requesting = True

            # MA 정배열 체크
            if self.config.ENABLE_MA_ALIGNMENT:
                is_aligned = check_ma_alignment(
                    self.kiwoom, code, self.config.MA_TICK, self.config.MA_PERIODS
                )
                if not is_aligned:
                    return
                self.log(f"✅ {code} - MA 정배열 필터 통과")

            # 거래원 매도 우위 체크
            if self.config.ENABLE_TRADER_SELL:
                is_sell_dominant = check_trader_sell_dominance(
                    self.kiwoom, code, self.config.TRADER_CODE
                )
                if not is_sell_dominant:
                    return
                self.log(f"✅ {code} - 거래원 매도 우위 필터 통과")

            # 모든 필터 통과 시 최종 알림 실행
            self._execute_final_alert(
                code,
                payload['current_minute'],
                payload['candle'],
                payload['data'],
                payload['exec_time_str']
            )
        finally:
            self.is_requesting = False

    def _execute_final_alert(self, code: str, current_minute: str, candle: CandleData, data: Tuple, exec_time_str: str):
        """(메인 스레드에서 실행) 최종 알림을 생성하고 발송"""
        current_amount, avg_prev_amount, ratio, program_rank = data
        # HH:MM:SS
        time = f"{exec_time_str[:2]}:{exec_time_str[2:4]}:{exec_time_str[4:6]}"

        # 종목명 조회
        name = self.kiwoom.GetMasterCodeName(code)

        alert = AlertInfo(
            time=time,
            code=code,
            name=name,
            candle=candle,
            current_amount=current_amount,
            avg_prev_amount=avg_prev_amount,
            ratio=ratio,
            program_rank=program_rank
        )

        # 알림 기록
        self.alerted[code] = current_minute

        # 로그 출력
        message = self._get_alert_text(alert)
        self.log(message)

        # 텔레그램 메시지 전송
        if self.telegram_bot:
            self.telegram_bot.send_alert(message)


def main():
    """애플리케이션 진입점"""
    config = Config()
    bot = NBunBot(config)

    try:
        bot.start()
    except KeyboardInterrupt:
        print("\nCtrl+C 입력. 종료합니다.")
    finally:
        bot.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 예기치 않은 오류 발생: {e}")
        traceback.print_exc()
