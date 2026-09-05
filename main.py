import os
import re
import html
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from telegram_helper import TelegramHelper
from gemini_helper import GeminiHelper
from leetcode_helper import LeetCodeHelper

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LEETCODE_CATEGORY_SLUG = os.getenv("LEETCODE_CATEGORY_SLUG", "all-code-essentials")

if not TELEGRAM_BOT_TOKEN:
    logging.warning("Missing TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    logging.warning("Missing GEMINI_API_KEY")

telegram = TelegramHelper(bot_token=TELEGRAM_BOT_TOKEN)
gemini = GeminiHelper(api_key=GEMINI_API_KEY)
leetcode = LeetCodeHelper(category_slug=LEETCODE_CATEGORY_SLUG)

# Telegram hard message limit.
TELEGRAM_MAX_CHARS = 4096
# Budget for the Gemini summary, leaving room for the header line.
SUMMARY_CHAR_BUDGET = 4000

# Map a single digit in the message to a LeetCode difficulty.
DIFFICULTY_MAP = {"1": "EASY", "2": "MEDIUM", "3": "HARD"}

USAGE_TEXT = (
    "Gửi 1, 2 hoặc 3 để nhận một câu hỏi LeetCode:\n"
    "1 = EASY\n"
    "2 = MEDIUM\n"
    "3 = HARD"
)


def parse_difficulty(text: str) -> str | None:
    """Return EASY/MEDIUM/HARD if the message contains a lone 1, 2 or 3."""
    match = re.search(r"\b([123])\b", text)
    if match:
        return DIFFICULTY_MAP[match.group(1)]
    return None


def send_spoiler(chat_id: int, heading: str, body: str):
    """
    Send `body` as a Telegram spoiler (blurred until tapped), prefixed by a
    visible `heading`. Uses HTML parse mode; body is HTML-escaped so code
    containing <, >, & does not break parsing. Truncated to the message limit.
    """
    escaped = html.escape(body)
    # Reserve room for the heading, a blank line, and the <tg-spoiler> tags.
    overhead = len(heading) + len("\n\n") + len("<tg-spoiler></tg-spoiler>")
    max_body = TELEGRAM_MAX_CHARS - overhead
    if len(escaped) > max_body:
        escaped = escaped[: max_body - 1] + "…"
    message = f"{heading}\n\n<tg-spoiler>{escaped}</tg-spoiler>"
    telegram.send_message(chat_id, message, parse_mode="HTML")


def handle_message(chat_id: int, text: str):
    difficulty = parse_difficulty(text)
    if not difficulty:
        telegram.send_message(chat_id, USAGE_TEXT)
        return

    # 1. Random question for the chosen difficulty.
    random_q = leetcode.get_random_question(difficulty)
    if not random_q or not random_q.get("titleSlug"):
        telegram.send_message(chat_id, "Không lấy được câu hỏi lúc này. Vui lòng thử lại.")
        return

    title_slug = random_q["titleSlug"]

    # 2. Full details for that question.
    details = leetcode.get_question_details(title_slug)
    if not details or not details.get("content"):
        telegram.send_message(chat_id, "Không lấy được nội dung câu hỏi lúc này. Vui lòng thử lại.")
        return

    title = details.get("title", random_q.get("title", ""))
    diff = details.get("difficulty", difficulty)
    link = f"https://leetcode.com/problems/{title_slug}/"

    # 3. Summarize the full requirement in easy Vietnamese via Gemini.
    try:
        summary = gemini.summarize_question(title, details["content"], char_budget=SUMMARY_CHAR_BUDGET)
    except Exception:
        logging.exception("Gemini summarization failed")
        telegram.send_message(chat_id, "Không thể tóm tắt câu hỏi lúc này. Vui lòng thử lại.")
        return

    # 4. Send plain text: header + summary, truncated defensively.
    header = f"[{diff}] {title}\n{link}\n\n"
    message = header + summary
    if len(message) > TELEGRAM_MAX_CHARS:
        message = message[: TELEGRAM_MAX_CHARS - 1] + "…"
    telegram.send_message(chat_id, message)

    # 5. Generate the answer via Gemini and send it as two spoiler messages
    #    (blurred until the user taps to reveal): explanation, then code.
    try:
        solution = gemini.solve_question(title, details["content"])
    except Exception:
        logging.exception("Gemini solve failed")
        telegram.send_message(chat_id, "Không tạo được lời giải lúc này.")
        return

    explanation = solution.get("explanation", "").strip()
    code = solution.get("code", "").strip()

    if explanation:
        send_spoiler(chat_id, "💡 Lời giải (chạm để xem):", explanation)
    if code:
        send_spoiler(chat_id, "🐍 Python (chạm để xem):", code)


@app.route("/", methods=["GET"])
def index():
    return "OK", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    if TELEGRAM_WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != TELEGRAM_WEBHOOK_SECRET:
            return jsonify({"ok": False, "reason": "invalid secret"}), 200

    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"ok": False, "reason": "empty payload"}), 200

    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return jsonify({"ok": False, "reason": "no message"}), 200

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
        telegram.send_message(chat_id, "Vui lòng gửi một tin nhắn văn bản.")
        return jsonify({"ok": False, "reason": "no text"}), 200

    logging.info(f"[webhook] chat_id={chat_id} text={text!r}")

    try:
        handle_message(chat_id, text)
    except Exception:
        logging.exception(f"Error handling message from chat_id={chat_id}")
        telegram.send_message(chat_id, "Đã có lỗi xảy ra. Vui lòng thử lại.")

    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
