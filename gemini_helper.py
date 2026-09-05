import os
import re
import time
import logging
import requests
from llm_base import LLMHelper

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# HTTP status codes worth retrying (transient server / rate-limit errors).
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GeminiHelper(LLMHelper):
    def __init__(self, api_key: str, max_retries: int = 3, base_delay: float = 1.0):
        self.api_key = api_key
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _generate(self, prompt: str, max_output_tokens: int, temperature: float) -> str:
        url = GEMINI_API_URL.format(model=self.model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "temperature": temperature,
            },
        }

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    url, json=payload, params={"key": self.api_key}, timeout=30
                )
                resp.raise_for_status()
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status not in RETRYABLE_STATUS:
                    raise  # permanent error (400/401/403/404...) — don't retry
                last_exc = exc
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc  # transient network error — retry

            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** attempt)  # exponential backoff
                logging.warning(
                    "Gemini request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, self.max_retries + 1, delay, last_exc,
                )
                time.sleep(delay)

        raise RuntimeError(f"Gemini request failed after {self.max_retries + 1} attempts") from last_exc

    def summarize_question(self, title: str, content: str, char_budget: int = 4000) -> str:
        """
        Ask Gemini to summarize a LeetCode question's full requirement in an
        easy-to-understand way, in Vietnamese, as plain text within char_budget.
        The content is raw HTML from LeetCode; Gemini is instructed to read it
        and produce a clean plain-text summary.
        """
        prompt = (
            "Bạn là một mentor luyện phỏng vấn coding. Dưới đây là đề bài của một câu hỏi "
            "LeetCode (nội dung ở dạng HTML). Hãy đọc và tóm tắt lại TOÀN BỘ yêu cầu của đề "
            "một cách dễ hiểu bằng tiếng Việt, sao cho người đi phỏng vấn nắm được đầy đủ đề bài "
            "mà không cần đọc bản gốc.\n\n"
            f"Tên bài: {title}\n\n"
            f"Nội dung (HTML):\n{content}\n\n"
            "Yêu cầu về câu trả lời:\n"
            "- Viết bằng tiếng Việt, văn phong đơn giản, rõ ràng.\n"
            "- Giữ nguyên các thuật ngữ kỹ thuật tiếng Anh phổ biến (array, string, hash map, "
            "linked list, binary tree, v.v.) nếu cần.\n"
            "- Trình bày: mô tả bài toán, input, output, ràng buộc (constraints), và 1 ví dụ minh họa.\n"
            "- CHỈ dùng plain text, TUYỆT ĐỐI không dùng markdown hay HTML.\n"
            f"- Giữ độ dài dưới {char_budget} ký tự."
        )
        return self._generate(prompt, max_output_tokens=2000, temperature=0.3)

    def solve_question(self, title: str, content: str) -> dict:
        """
        Ask Gemini to solve a LeetCode question. Returns
        {"explanation": str, "code": str, "language": str} where:
          - explanation: Vietnamese plain text — how to identify the problem
            type and the step-by-step approach to solve it.
          - code: the solution as plain text.
          - language: the language of the solution, "Python" or "MySQL".
        The language is chosen by the model: Python by default, but MySQL if the
        question is a database/SQL problem. The parts use explicit delimiters.
        """
        exp_start, exp_end = "===EXPLANATION_START===", "===EXPLANATION_END==="
        code_start, code_end = "===CODE_START===", "===CODE_END==="
        lang_start, lang_end = "===LANGUAGE_START===", "===LANGUAGE_END==="
        prompt = (
            "Bạn là một mentor luyện phỏng vấn coding. Dưới đây là đề bài của một câu hỏi "
            "LeetCode (nội dung ở dạng HTML). Hãy giải bài này.\n\n"
            f"Tên bài: {title}\n\n"
            f"Nội dung (HTML):\n{content}\n\n"
            "Chọn ngôn ngữ cho lời giải theo quy tắc: mặc định dùng Python; "
            "nhưng nếu đề bài là bài toán về cơ sở dữ liệu / SQL (ví dụ yêu cầu viết một câu truy vấn "
            "trên các bảng dữ liệu) thì dùng MySQL.\n\n"
            "Trả về CHÍNH XÁC theo định dạng sau (giữ nguyên các dòng phân cách):\n"
            f"{lang_start}\n"
            "<chỉ ghi 'Python' hoặc 'MySQL'>\n"
            f"{lang_end}\n"
            f"{exp_start}\n"
            "<phần giải thích bằng tiếng Việt: (1) cách nhận diện dạng bài (problem type), "
            "(2) các bước để giải bài toán. Dùng plain text, không markdown, không HTML. "
            "Giữ nguyên thuật ngữ kỹ thuật tiếng Anh phổ biến (hash map, two pointers, JOIN, GROUP BY, v.v.).>\n"
            f"{exp_end}\n"
            f"{code_start}\n"
            "<code hoàn chỉnh bằng đúng ngôn ngữ đã chọn ở trên để giải bài, chỉ code thuần, "
            "không giải thích, không markdown, không dùng dấu ``` >\n"
            f"{code_end}"
        )
        text = self._generate(prompt, max_output_tokens=3000, temperature=0.2)

        language = self._extract(text, lang_start, lang_end)
        explanation = self._extract(text, exp_start, exp_end)
        code = self._extract(text, code_start, code_end)

        # Strip stray markdown code fences if the model added them anyway.
        code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
        code = re.sub(r"\n?```$", "", code).strip()

        # Normalize language to one of the two supported values, default Python.
        language = "MySQL" if "sql" in language.lower() else "Python"

        return {
            "explanation": explanation or text.strip(),
            "code": code,
            "language": language,
        }

    @staticmethod
    def _extract(text: str, start_marker: str, end_marker: str) -> str:
        """Return the text between start_marker and end_marker, or '' if absent."""
        start = text.find(start_marker)
        if start == -1:
            return ""
        start += len(start_marker)
        end = text.find(end_marker, start)
        if end == -1:
            return text[start:].strip()
        return text[start:end].strip()
