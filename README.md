# Gold Price Telegram Bot
#### Video Demo: <https://youtu.be/V6YMj8Dff7o>
#### Description:

Gold Price Telegram Bot is a small Python program that checks the live international gold spot price (XAU/USD) every 30 minutes and automatically posts a formatted update to a Telegram channel. It was built as my final project for CS50's Introduction to Programming with Python (CS50P), and it draws on nearly everything covered in the course: working with a web API (`requests`), reading configuration from the environment, string formatting, exception handling, an infinite polling loop, and a test suite written with `pytest`.

## Why this project?

Gold is widely followed as a store of value, and its price changes throughout the trading day. Rather than opening a website or app to check it, I wanted a lightweight bot that pushes the current price straight into a Telegram channel on a fixed schedule, so anyone subscribed to the channel sees an update without having to look anything up themselves.

## How it works

At a high level, the bot repeats the following cycle every 30 minutes:

1. It calls the [GoldAPI.io](https://www.goldapi.io) REST API to fetch the current XAU/USD spot price, along with the price per gram of 24-karat gold and the percentage change for the day.
2. It extracts just the fields it needs from that response.
3. It formats those numbers into a short, readable Persian-language message with an up/down arrow depending on whether the price moved up or down.
4. It sends that message to a Telegram channel using Telegram's Bot API (`sendMessage`).
5. It waits 30 minutes and repeats, catching and logging any error along the way (a failed request one cycle should not crash the whole bot).

## Files

- **`project.py`** contains all of the program's logic. Besides `main`, it defines six additional functions:
  - `get_gold_price(api_key)` calls the GoldAPI.io endpoint and returns the raw JSON response as a dictionary. This is the only function that talks to the gold price API.
  - `get_ai_commentary(current_price_usd, previous_price_usd, change_pct, toman_price=None)` calls the Google Gemini API via REST to obtain a short, natural Persian commentary on price movement. It handles errors gracefully by returning an empty string if the call fails or if the API key is missing.
  - `parse_price(data)` is a **pure function**: given a dictionary (the API's response), it returns a small, clean dictionary with just the three values the rest of the program cares about (`ounce_usd`, `gram_24k_usd`, `change_percent`). Because it does no I/O, it's trivial to unit test with fake input.
  - `format_message(price_info)` is also a pure function. It takes that clean price dictionary and returns the exact string that will be posted to Telegram, including an emoji arrow, optional AI commentary, and a timestamp.
  - `build_telegram_payload(chat_id, text)` is a third pure function; it builds the dictionary of form data that Telegram's API expects, separating "what to send" from "actually sending it."
  - `send_telegram_message(bot_token, payload)` performs the actual HTTP POST to Telegram and is the only function that talks to the Telegram API.
- **`test_project.py`** contains `pytest` tests for the pure functions and unit tests for `get_ai_commentary` (mocking the REST call for both success and failure cases).
- **`requirements.txt`** lists the two third-party packages the project depends on: `requests` (for HTTP calls) and `python-dotenv` (for loading secrets from a local `.env` file instead of hard-coding them).
- **`.env.example`** documents which environment variables the program expects (`GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `GEMINI_API_KEY`) without containing any real secrets, so it's safe to commit to version control. A real `.env` file (which is not committed) supplies the actual values.

## AI Market Commentary (Gemini Integration)

The bot incorporates short AI-generated Persian market commentary into the posted message using Google's Gemini API via REST (`generateContent`).
- **REST Call**: Sends current price, previous price, percent change, and optional Toman price directly to Gemini via HTTP POST without local SDKs or proxies.
- **Graceful Fallback**: The request has a ~10-second timeout and is wrapped in exception handling. If the API key (`GEMINI_API_KEY`) is omitted, or if the API fails or times out, the function returns an empty string, allowing the bot to post the core price update without crashing.
- **GitHub Secret**: To enable AI commentary in automated workflow runs, a `GEMINI_API_KEY` repository secret must be added to your GitHub repository secrets.

## Design decisions

I chose to read all secrets (API keys and tokens) from environment variables rather than hard-coding them, both because it's unsafe to commit credentials to a public GitHub repository, and because it makes the same code portable to any server without editing the source.

I split the "get data," "transform data," and "send data" responsibilities into separate, small functions instead of one large `main` function. This was primarily so that the transformation logic (`parse_price`, `format_message`, `build_telegram_payload`) could be unit-tested in isolation, satisfying the project's testing requirement, without needing to mock network calls or expose real credentials just to run the test suite.

For scheduling, `main()` performs exactly one fetch-format-send cycle and then exits, rather than looping forever with `time.sleep`. Repetition every 30 minutes is handled by an external scheduler instead: a GitHub Actions workflow (`.github/workflows/gold-price.yml`) with a cron trigger (`*/30 * * * *`) checks out the repository and runs `python project.py` every 30 minutes, 24/7, using GitHub's own servers. I chose this over an in-process infinite loop because it doesn't require my own computer to stay on and connected at all times, and because a fresh process each run means a single failed request can't leave the bot stuck or crashed for good. The three secrets (`GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`) are stored as encrypted GitHub Actions repository secrets rather than committed in a `.env` file, and are injected as environment variables only for the duration of each scheduled run.

## How to run it

### Locally, once (for testing)
1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and note the token it gives you.
2. Add that bot as an administrator (with permission to post messages) to your Telegram channel.
3. Sign up for a free API key at [goldapi.io](https://www.goldapi.io).
4. Copy `.env.example` to `.env` and fill in your real `GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHANNEL_ID`.
5. Install dependencies: `pip install -r requirements.txt`
6. Run the bot once: `python project.py`
7. Run the tests: `pytest test_project.py`

### Continuously, every 30 minutes (deployment)
This repository includes `.github/workflows/gold-price.yml`, a GitHub Actions workflow that runs `project.py` every 30 minutes automatically, without needing my own computer to be on.
1. Push this project to a GitHub repository.
2. In the repository's Settings → Secrets and variables → Actions, add three repository secrets with the exact names `GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHANNEL_ID`.
3. That's it — GitHub will run the workflow on its own schedule from then on. It can also be triggered manually from the repository's Actions tab for testing.
