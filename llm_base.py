from abc import ABC, abstractmethod


class LLMHelper(ABC):
    @abstractmethod
    def summarize_question(self, title: str, content: str, char_budget: int = 3500) -> str:
        """
        Summarize a LeetCode question's full requirement in easy-to-understand
        Vietnamese plain text, kept within char_budget characters.
        """

    @abstractmethod
    def solve_question(self, title: str, content: str) -> dict:
        """
        Solve a LeetCode question. Returns {"explanation": str, "code": str}:
        explanation is Vietnamese plain text (problem-type identification and
        step-by-step approach); code is a Python solution as plain text.
        """
