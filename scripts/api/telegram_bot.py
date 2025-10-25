"""
Telegram Bot 알림 시스템
거래 알림을 Telegram으로 전송
"""
from datetime import datetime
from typing import Optional, Dict, Callable
import requests


class TelegramBot:
    """Telegram Bot 알림 클래스"""

    def __init__(self, token: str, chat_id: str, logger: Optional[Callable[[str], None]] = None):
        """
        Args:
            token: Telegram Bot Token
            chat_id: Telegram Chat ID
            logger: 로그 출력 함수 (선택)
        """
        self.token = token
        self.chat_id = chat_id
        self.logger = logger or print
        self.is_connected = False

    def connect(self) -> bool:
        """
        Telegram Bot 연결 및 검증

        Returns:
            bool: 연결 성공 여부
        """
        try:
            url = f"https://api.telegram.org/bot{self.token}/getMe"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                bot_info = response.json()
                bot_username = bot_info.get(
                    'result', {}).get('username', 'Unknown')
                self.logger(f"✅ Telegram Bot 연결 성공: @{bot_username}")
                self.is_connected = True
                return True
            else:
                raise Exception(f"HTTP {response.status_code}")

        except Exception as e:
            self.logger(f"❌ Telegram Bot 연결 실패: {str(e)}")
            self.is_connected = False
            return False

    def send_alert(self, message: str):
        """
        거래 알림 전송

        Args:
            message: 알림 메시지 (Markdown 형식)
        """
        if not self.is_connected:
            return

        try:
            self._send_message(message)

        except Exception as e:
            self.logger(f"❌ Telegram 알림 전송 오류: {str(e)}")

    def send_start_message(self, message_body: str):
        """
        모니터링 시작 메시지 전송

        Args:
            message_body: 시작 시간 외의 메시지 본문
        """
        if not self.is_connected:
            return

        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            message = (
                f"✅ *모니터링 시작*\n\n"
                f"⏰ *시작 시간:* {current_time}\n"
                f"{message_body}"
            )

            self._send_message(message)

        except Exception as e:
            self.logger(f"❌ Telegram 시작 메시지 전송 오류: {str(e)}")

    def send_stop_message(self):
        """
        모니터링 종료 메시지 전송
        """
        if not self.is_connected:
            return

        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            message = (
                f"✅ *모니터링 종료*\n\n"
                f"*종료 시간:* {current_time}\n"
            )

            self._send_message(message)

        except Exception as e:
            self.logger(f"❌ Telegram 종료 메시지 전송 오류: {str(e)}")

    def _send_message(self, message: str):
        """
        Telegram API 호출 (내부 메서드)

        Args:
            message: 전송할 메시지 (Markdown 형식)
        """
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }

            response = requests.post(url, json=data, timeout=5)

            if response.status_code != 200:
                error_msg = response.json().get('description', 'Unknown error')
                self.logger(f"❌ Telegram 메시지 전송 실패: {error_msg}")

        except Exception as e:
            raise e
