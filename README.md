# leetcode-study

A Telegram bot that sends you a random [LeetCode](https://leetcode.com) question
by difficulty, then uses Google Gemini to summarize the **full requirement** in
easy-to-understand Vietnamese (plain text, within Telegram's message limit).

## How it works

1. `GET /` — health check, returns `OK` with HTTP 200.
2. `POST /webhook` — receives Telegram updates. Send the bot a message containing:
   - `1` → EASY
   - `2` → MEDIUM
   - `3` → HARD

   Anything else gets a short usage reply.
3. The bot queries the LeetCode GraphQL API for a random question of the chosen
   difficulty (`randomQuestion`), then fetches its full details (`question`).
4. The question content (HTML) is passed to Gemini, which returns an
   easy-to-read Vietnamese summary covering the problem, input, output,
   constraints, and an example.
5. The bot replies with `[difficulty] title`, the problem link, and the summary
   as plain text (defensively truncated at Telegram's 4096-character limit).

## Project structure

```
leetcode-study/
├── main.py              # Flask app: GET / and POST /webhook
├── leetcode_helper.py   # LeetCode GraphQL calls (random question + details)
├── gemini_helper.py     # Gemini summarization (Vietnamese, plain text)
├── llm_base.py          # LLMHelper abstract base
├── telegram_helper.py   # Telegram sendMessage wrapper
├── pyproject.toml       # dependencies
└── env.example          # environment variable template
```

## Configuration

Copy `env.example` to `.env` and fill in the values:

| Variable                 | Required | Description                                          |
| ------------------------ | -------- |------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`     | yes      | Bot token from [@BotFather](https://t.me/BotFather). |
| `TELEGRAM_WEBHOOK_SECRET`| no       | Shared secret; validated against the webhook header. |
| `GEMINI_API_KEY`         | yes      | Google Gemini API key.                               |
| `GEMINI_MODEL`           | no       | Gemini model (default `gemini-3.5-flash`).           |
| `LEETCODE_CATEGORY_SLUG` | no       | LeetCode category (default `all-code-essentials`).   |
| `PORT`                   | no       | Port to bind (default `8080`).                       |

## Running locally

Using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
cp env.example .env   # then edit .env with your tokens
uv run python main.py
```

The app listens on `http://0.0.0.0:8080`.

For a production-style run with gunicorn:

```bash
uv run gunicorn main:app --bind 0.0.0.0:8080 --workers 2 --timeout 60
```

## Connecting the Telegram webhook

Once the app is publicly reachable (e.g. deployed, or via a tunnel), register the
webhook with Telegram. Replace the placeholders with your bot token, public URL,
and (optional) secret:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<YOUR_PUBLIC_HOST>/webhook",
    "allowed_updates": ["message"],
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
  }'
```

Then message the bot `1`, `2`, or `3` to receive a question.

## LeetCode API reference

The bot uses two GraphQL queries against `https://leetcode.com/graphql`:

- `randomQuestion(categorySlug, filters)` — picks a random question, filtered by
  difficulty, and returns its `titleSlug`.
- `question(titleSlug)` — returns the question `title`, `difficulty`, and
  `content` (HTML) used for the summary.

No LeetCode account or authentication is required; the requests only set a
browser-like `User-Agent` header.
