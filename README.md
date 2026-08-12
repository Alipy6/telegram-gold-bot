# Gold Price Telegram Bot
#### Video Demo: https://youtu.be/V6YMj8Dff7o
#### Description:

Gold Price Telegram Bot is a small Python program that checks the live international gold spot price (XAU/USD) every 30 minutes and automatically posts a formatted update to a Telegram channel, optionally including the Tehran market price of Tether (USDT) in Toman as well. It was built as my final project for CS50's Introduction to Programming with Python (CS50P), and it draws on nearly everything covered in the course: working with web APIs (`requests`), reading configuration from the environment, string formatting, exception handling, scheduled automation with GitHub Actions, and a test suite written with `pytest`.

## Why this project?

Gold is widely followed as a store of value, and its price changes throughout the trading day. Rather than opening a website or app to check it, I wanted a lightweight bot that pushes the current price straight into a Telegram channel on a fixed schedule, so anyone subscribed to the channel sees an update without having to look anything up themselves.

## How it works

Every 30 minutes, an external scheduler (see "Design decisions" below) starts the program, which performs the following cycle once and then exits:

1. It calls the [GoldAPI.io](https://www.goldapi.io) REST API to fetch the current XAU/USD spot price, along with the price per gram of 24-karat gold and the percentage change for the day.
2. It extracts just the fields it needs from that response.
3. If a `BRSAPI_KEY` is configured, it also calls [brsapi.ir](https://brsapi.ir) to fetch the current Tehran market price of Tether (USDT) in Toman. This step is optional and best-effort: if the key is missing or the request fails, the bot logs a warning and simply continues without it.
4. It formats those numbers into a short, readable Persian-language message with an up/down arrow depending on whether each price moved up or down.
5. It sends that message to a Telegram channel using Telegram's Bot API (`sendMessage`).
6. If any step fails, the error is caught, logged, and reported with a non-zero exit code; the next scheduled run 30 minutes later is unaffected.

## Files

- **`project.py`** contains all of the program's logic. Besides `main`, it defines seven additional functions:
  - `get_gold_price(api_key)` calls the GoldAPI.io endpoint and returns the raw JSON response as a dictionary. This is the only function that talks to the gold price API.
  - `parse_price(data)` is a **pure function**: given a dictionary (the API's response), it returns a small, clean dictionary with just the three values the rest of the program cares about (`ounce_usd`, `gram_24k_usd`, `change_percent`). Because it does no I/O, it's trivial to unit test with fake input.
  - `get_iran_prices(api_key)` calls the brsapi.ir endpoint and returns its raw JSON response (gold, currency, and cryptocurrency prices in Toman). This is the only function that talks to that API.
  - `parse_tether_price(data)` is a **pure function** that finds the Tether (`USDT_IRT`) entry inside brsapi.ir's response and returns just its Toman price and percentage change.
  - `format_message(price_info, tether_info=None)` is also a pure function. It takes the clean price dictionary (and, optionally, the Tether info) and returns the exact string that will be posted to Telegram, including emoji arrows and a timestamp. The Tether section is only included when `tether_info` is provided.
  - `build_telegram_payload(chat_id, text)` is a pure function; it builds the dictionary of form data that Telegram's API expects, separating "what to send" from "actually sending it."
  - `send_telegram_message(bot_token, payload)` performs the actual HTTP POST to Telegram and is the only function that talks to the Telegram API.
- **`test_project.py`** contains `pytest` tests for the four pure functions above (`parse_price`, `parse_tether_price`, `format_message`, and `build_telegram_payload`), including cases that check `format_message` both with and without Tether data. I deliberately designed the program so that the functions doing actual network I/O (`get_gold_price`, `get_iran_prices`, and `send_telegram_message`) are as small and separate as possible, and all of the interesting logic — parsing and formatting — lives in functions that can be tested with plain dictionaries and strings, with no network connection or API keys required to run the test suite.
- **`requirements.txt`** lists the two third-party packages the project depends on: `requests` (for HTTP calls) and `python-dotenv` (for loading secrets from a local `.env` file instead of hard-coding them).
- **`.env.example`** documents which environment variables the program expects (`GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, and the optional `BRSAPI_KEY`) without containing any real secrets, so it's safe to commit to version control. A real `.env` file (which is not committed) supplies the actual values.

## Design decisions

I chose to read all secrets (API keys and tokens) from environment variables rather than hard-coding them, both because it's unsafe to commit credentials to a public GitHub repository, and because it makes the same code portable to any server without editing the source.

I split the "get data," "transform data," and "send data" responsibilities into separate, small functions instead of one large `main` function. This was primarily so that the transformation logic (`parse_price`, `format_message`, `build_telegram_payload`) could be unit-tested in isolation, satisfying the project's testing requirement, without needing to mock network calls or expose real credentials just to run the test suite.

For scheduling, `main()` performs exactly one fetch-format-send cycle and then exits, rather than looping forever with `time.sleep`. Repetition every 30 minutes is handled by an external scheduler instead: a GitHub Actions workflow (`.github/workflows/gold-price.yml`) with a cron trigger (`*/30 * * * *`) checks out the repository and runs `python project.py` every 30 minutes, 24/7, using GitHub's own servers. I chose this over an in-process infinite loop because it doesn't require my own computer to stay on and connected at all times, and because a fresh process each run means a single failed request can't leave the bot stuck or crashed for good. The three required secrets (`GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`) are stored as encrypted GitHub Actions repository secrets rather than committed in a `.env` file, and are injected as environment variables only for the duration of each scheduled run.

The Tether price add-on is implemented as a "best-effort" step rather than a required one: `main()` only attempts it if `BRSAPI_KEY` is set, and wraps the attempt in its own `try`/`except` so that a missing key, an expired free-tier quota, or a temporary outage on brsapi.ir's side never prevents the core gold-price message from being sent. `format_message` reflects this by accepting `tether_info` as an optional argument that defaults to `None`, which is also why the existing tests for it continue to pass unchanged even though its signature grew.

## How to run it

### Locally, once (for testing)
1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and note the token it gives you.
2. Add that bot as an administrator (with permission to post messages) to your Telegram channel.
3. Sign up for a free API key at [goldapi.io](https://www.goldapi.io).
4. Copy `.env.example` to `.env` and fill in your real `GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHANNEL_ID`. Optionally, also get a free key from [brsapi.ir](https://brsapi.ir) and set `BRSAPI_KEY` to include the Tether/Toman line in the message.
5. Install dependencies: `pip install -r requirements.txt`
6. Run the bot once: `python project.py`
7. Run the tests: `pytest test_project.py`

### Continuously, every 30 minutes (deployment)
This repository includes `.github/workflows/gold-price.yml`, a GitHub Actions workflow that runs `project.py` every 30 minutes automatically, without needing my own computer to be on.
1. Push this project to a GitHub repository.
2. In the repository's Settings → Secrets and variables → Actions, add repository secrets with the exact names `GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHANNEL_ID` (required), and optionally `BRSAPI_KEY` (to enable the Tether/Toman line).
3. That's it — GitHub will run the workflow on its own schedule from then on. It can also be triggered manually from the repository's Actions tab for testing.
