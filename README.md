# Gold Price Telegram Bot

A Python bot that posts live global gold prices — plus their Iranian Toman
equivalents — to a Telegram channel every 30 minutes.

Built as the final project for Harvard's [CS50P](https://cs50.harvard.edu/python/).

## Overview

The bot fetches the current spot price of gold from [GoldAPI.io](https://www.goldapi.io/)
and, optionally, the Tether (USDT) exchange rate and Emami gold coin price
from [brsapi.ir](https://brsapi.ir/), then posts a formatted summary to a
Telegram channel. It's designed to run as a short-lived script triggered by
an external scheduler (GitHub Actions cron), rather than as a long-running
process.

## Features

- 🥇 **Global gold price** — per troy ounce and per gram (24k), in USD
- 💵 **Tether (USDT) price** in Toman
- 🥇 **18k gold price** per gram, in Toman (derived from the USD gold price
  and the Tether rate)
- 🟡 **Emami gold coin price** in Toman
- ⚠️ **Significant-change alerts** — a warning banner appears automatically
  when any price's daily change exceeds a configurable threshold (default: 2%)
- **Resilient by design** — if the Iranian price source (brsapi.ir) is
  unreachable, or one specific value can't be found in its response, the bot
  still posts the core gold price without failing outright. Each optional
  value (Tether, 18k Toman price, coin price) degrades independently.
- Fully **unit tested** (pytest) — all data-parsing and message-formatting
  logic is covered

## Example output

```
🥇 قیمت لحظه‌ای طلای جهانی
⚠️ نوسان قابل‌توجه: طلای جهانی، سکه امامی

هر اونس: 2650.40 دلار
هر گرم (۲۴ عیار): 85.20 دلار
تغییر: 🔺 2.70%

💵 تتر (USDT): 95,000 تومان
تغییر: 🔺 0.30%

🥇 طلای ۱۸ عیار: 6,070,500 تومان

🟡 سکه امامی: 62,000,000 تومان
تغییر: 🔻 3.10%

🕒 بروزرسانی: 2026-08-13 17:54
```

<!-- TODO: replace this with a real screenshot from the @Gold30m_up channel -->

## Tech stack

- Python 3.11+
- [`requests`](https://pypi.org/project/requests/) — HTTP calls to both APIs
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) — local `.env` config
- [`pytest`](https://pypi.org/project/pytest/) — testing
- GitHub Actions (`schedule` trigger) — runs the bot every 30 minutes without
  needing a server

## Project structure

```
.
├── project.py          # main script: fetch prices, format message, send to Telegram
├── test_project.py     # pytest test suite
├── requirements.txt    # runtime dependencies
├── .env.example         # template for local environment variables
└── .github/
    └── workflows/
        └── post-gold-price.yml   # scheduled GitHub Actions workflow
```

## Setup (local)

1. Clone the repo and create a virtual environment:
   ```bash
   git clone <your-repo-url>
   cd <your-repo>
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```

   | Variable | Required | Description |
   |---|---|---|
   | `GOLD_API_KEY` | Yes | API key from [goldapi.io](https://www.goldapi.io/) |
   | `TELEGRAM_BOT_TOKEN` | Yes | Bot token from [@BotFather](https://t.me/BotFather) |
   | `TELEGRAM_CHANNEL_ID` | Yes | Your Telegram channel's ID (e.g. `@your_channel`) |
   | `BRSAPI_KEY` | No | API key from [brsapi.ir](https://brsapi.ir/) — enables the Tether, 18k Toman, and coin price lines |

4. Run it:
   ```bash
   python project.py
   ```

## Running tests

```bash
pip install pytest
pytest test_project.py -v
```

All the data-parsing (`parse_price`, `parse_tether_price`,
`parse_gold_coin_price`) and pure calculation/formatting functions
(`calculate_18k_gold_toman`, `is_significant_change`, `format_message`) are
covered — the only untested parts are the three thin I/O functions that call
external APIs (`get_gold_price`, `get_iran_prices`, `send_telegram_message`),
by design.

## Deployment

The bot is designed to run on a schedule via **GitHub Actions**, so it needs
no server of its own:

1. Add `GOLD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, and
   `BRSAPI_KEY` as **repository secrets** (Settings → Secrets and variables →
   Actions).
2. The included workflow (`.github/workflows/post-gold-price.yml`) runs the
   script every 30 minutes.

## Notes & caveats

- The 18k-gram and Emami-coin Toman prices are **global-equivalent**
  conversions (spot price × Tether rate), not the exact retail price you'd
  see at an Iranian jewelry shop — local retail prices also factor in labor
  fees (اجرت), profit margin, and tax.
- brsapi.ir doesn't publish a stable documented `symbol` for the Emami coin,
  so `parse_gold_coin_price` matches by the Persian name (`امامی`) instead,
  which is more robust to minor API changes.

## License

MIT — feel free to use or adapt this for your own projects.
