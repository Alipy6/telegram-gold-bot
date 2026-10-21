# 🥇 Gold, Currency & Coin Market Telegram Bot (CS50P Final Project)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-17_Passed-10b981?logo=pytest&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/Scheduler-GitHub_Actions_(Hourly)-2088FF?logo=githubactions&logoColor=white)
![Gemini AI](https://img.shields.io/badge/AI_Analyst-Google_Gemini-8E75B2?logo=googlegemini&logoColor=white)

#### 🎥 Video Demo: <https://youtu.be/V6YMj8Dff7o>

## 📌 Overview
**Gold Price Telegram Bot** is an automated financial market reporter and AI commentary engine built in Python. Originally developed as my final project for **Harvard University's CS50's Introduction to Programming with Python (CS50P)**, it fetches live international gold spot prices (`XAU/USD`), domestic Iranian exchange rates (`USDT/IRT`), and **Emami Gold Coin** prices every hour, computes **18K gold valuation**, **24-hour rolling changes**, and **intrinsic coin bubble percentages**, generates concise Persian market analysis via **Google Gemini AI**, and broadcasts a structured HTML report to a Telegram channel.

---

## ✨ Key Features

- **🌎 Global & Domestic Market Aggregation**:
  - Fetches real-time international spot gold (`XAU/USD`) and 24K gram prices from `api.gold-api.com`.
  - Queries `BrsApi.ir` for live **Tether (`USDT/IRT`)** and **Emami Gold Coin (`سکه امامی`)** market prices and daily percentage fluctuations.
- **🧮 Financial & Intrinsic Valuation Math**:
  - **Calculated 18K Gold (`طلای ۱۸ عیار`)**: Converts 24K USD gram prices into Iranian Tomans using live USDT rates ($\text{Gram}_{24\text{K}} \times \text{USDT} \times 0.75$).
  - **Emami Coin Bubble Calculator (`حباب سکه`)**: Computes the exact intrinsic gold value of an Emami coin ($8.133\text{g} \times 0.900\text{ purity}$) and reports both the nominal Toman bubble and percentage premium.
  - **24-Hour Rolling Spot Change**: Tracks hourly spot prices in `gold_price_history.json` (with automatic 14-day pruning) to compute accurate 24-hour XAU/USD percentage changes.
  - **Volatility Alerts (`⚠️ نوسان قابل‌توجه`)**: Automatically flags assets experiencing $\ge 2.0\%$ movement.
- **🤖 AI Market Commentary (Google Gemini REST Integration)**:
  - Synthesizes global spot gold, Tether/Toman, and Emami coin movements into a natural 1–2 sentence Persian analytical summary using Gemini (`generateContent`), with graceful timeout/error fallbacks.
- **⏰ Serverless Hourly Automation**:
  - Powered 24/7 by a **GitHub Actions** cron workflow (`0 * * * *`) that runs the `pytest` verification suite, dispatches the Telegram update formatted in Tehran time (`IRST +03:30`), and commits the updated rolling price history.

---

## 🗂️ Project Architecture

- **`project.py`** — Core application logic and pure data transformation functions:
  - `get_gold_price(api_key)` & `get_iran_prices(api_key)`: External REST API clients with timeout and custom User-Agent protection.
  - `parse_price(data, history)`, `parse_tether_price(data)`, `parse_gold_coin_price(data)`: Pure parsers extracting normalized market dictionaries.
  - `calculate_18k_gold_toman(...)` & `calculate_coin_bubble(...)`: Pure financial valuation functions.
  - `calculate_24h_change(...)`, `load_price_history(...)`, `record_price_history(...)`: Rolling 24h delta engine with automatic 14-day history pruning.
  - `get_ai_commentary(...)`: Google Gemini REST client with graceful fallback.
  - `format_message(...)` & `build_telegram_payload(...)`: Pure HTML message builders for Telegram's Bot API.
- **`test_project.py`** — Comprehensive **`pytest`** unit test suite covering all pure functions, history calculations, coin bubble math, and mocked Gemini API responses.
- **`.github/workflows/gold-price.yml`** — Hourly CI/CD & cron automation pipeline.

---

## 🚀 Setup & Deployment

### 1. Local Execution
```bash
git clone [https://github.com/Alipy6/telegram-gold-bot.git](https://github.com/Alipy6/telegram-gold-bot.git)
cd telegram-gold-bot
pip install -r requirements.txt
cp .env.example .env   # Fill in your API keys
pytest test_project.py -v
python project.py

2. GitHub Actions 24/7 AutomationAdd the following encrypted secrets under Settings $\to$ Secrets and variables $\to$ Actions:TELEGRAM_BOT_TOKEN (Required)TELEGRAM_CHANNEL_ID (Required, e.g., @your_channel)BRSAPI_KEY (Optional — enables Tether, 18K Gold, and Emami Coin reporting)GEMINI_API_KEY (Optional — enables AI Persian market commentary)