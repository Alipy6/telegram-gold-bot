import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GOLD_API_URL = "https://www.goldapi.io/api/XAU/USD"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def main():
    
    gold_api_key = os.getenv("GOLD_API_KEY")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")

    if not all([gold_api_key, bot_token, channel_id]):
        sys.exit(
            "Missing one of GOLD_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID "
            "(check your .env file locally, or your repo secrets on GitHub Actions)."
        )

    try:
        data = get_gold_price(gold_api_key)
        price_info = parse_price(data)
        message = format_message(price_info)
        payload = build_telegram_payload(channel_id, message)
        send_telegram_message(bot_token, payload)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Sent: {message!r}")
    except Exception as e:
        sys.exit(f"Failed to post gold price: {e}")


def get_gold_price(api_key):
    response = requests.get(
        GOLD_API_URL,
        headers={"x-access-token": api_key},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def parse_price(data):
    return {
        "ounce_usd": data["price"],
        "gram_24k_usd": data["price_gram_24k"],
        "change_percent": data["chp"],
    }


def format_message(price_info):
    arrow = "🔺" if price_info["change_percent"] >= 0 else "🔻"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"<b>🥇 قیمت لحظه‌ای طلای جهانی</b>\n\n"
        f"هر اونس: {price_info['ounce_usd']:.2f} دلار\n"
        f"هر گرم (۲۴ عیار): {price_info['gram_24k_usd']:.2f} دلار\n"
        f"تغییر: {arrow} {abs(price_info['change_percent']):.2f}%\n\n"
        f"🕒 بروزرسانی: {now}"
    )


def build_telegram_payload(chat_id, text):
    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }


def send_telegram_message(bot_token, payload):
    url = TELEGRAM_API_URL.format(token=bot_token)
    response = requests.post(url, data=payload, timeout=10)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    main()
