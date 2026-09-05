import requests

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

RANDOM_QUESTION_QUERY = (
    "query randomQuestion($categorySlug: String, $filters: QuestionListFilterInput) { "
    "randomQuestion(categorySlug: $categorySlug, filters: $filters) { title titleSlug difficulty } }"
)

QUESTION_DETAILS_QUERY = (
    "query getQuestionDetails($titleSlug: String!) { "
    "question(titleSlug: $titleSlug) { title difficulty content codeSnippets { lang langSlug code } } }"
)

# LeetCode blocks requests without a browser-like User-Agent.
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://leetcode.com",
}


class LeetCodeHelper:
    def __init__(self, category_slug: str = "all-code-essentials"):
        self.category_slug = category_slug

    def get_random_question(self, difficulty: str) -> dict | None:
        """
        Fetch a random question for the given difficulty ("EASY" | "MEDIUM" | "HARD").
        Returns {"title", "titleSlug", "difficulty"} or None.
        """
        payload = {
            "query": RANDOM_QUESTION_QUERY,
            "variables": {
                "categorySlug": self.category_slug,
                "filters": {"difficulty": difficulty.upper()},
            },
        }
        resp = requests.post(LEETCODE_GRAPHQL_URL, json=payload, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("randomQuestion")

    def get_question_details(self, title_slug: str) -> dict | None:
        """
        Fetch full details for a question by its titleSlug.
        Returns {"title", "difficulty", "content", "codeSnippets": [...]} or None.
        """
        payload = {
            "query": QUESTION_DETAILS_QUERY,
            "variables": {"titleSlug": title_slug},
        }
        resp = requests.post(LEETCODE_GRAPHQL_URL, json=payload, headers=DEFAULT_HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("question")
