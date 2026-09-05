import requests


class TelegramHelper:
    def __init__(self, bot_token: str):
        self.api_base = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, chat_id: int, text: str, parse_mode: str = None):
        body = {"chat_id": chat_id, "text": text}
        if parse_mode:
            body["parse_mode"] = parse_mode
        resp = requests.post(f"{self.api_base}/sendMessage", json=body, timeout=10)
        resp.raise_for_status()
        return resp.json()
