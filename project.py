import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GOLD_API_URL = "https://api.gold-api.com/price/XAU"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

SIGNIFICANT_CHANGE_THRESHOLD = 2.0


def main():
    gold_api_key = os.getenv("GOLD_API_KEY")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    brsapi_key = os.getenv("BRSAPI_KEY")

    if not all([bot_token, channel_id]):
        sys.exit(
            "Missing required environment variables TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID "
            "(check your .env file locally, or your repo secrets on GitHub Actions)."
        )

    try:
        data = get_gold_price(gold_api_key)
        price_info = parse_price(data)

        tether_info = None
        coin_info = None
        if brsapi_key:
            try:
                iran_data = get_iran_prices(brsapi_key)
            except Exception as e:
                iran_data = None
                print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Warning: brsapi.ir unavailable: {e}")

            if iran_data is not None:
                try:
                    tether_info = parse_tether_price(iran_data)
                except Exception as e:
                    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Warning: Tether price unavailable: {e}")
                try:
                    coin_info = parse_gold_coin_price(iran_data)
                except Exception as e:
                    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Warning: Coin price unavailable: {e}")

        toman_price = tether_info["toman"] if tether_info else None
        commentary = get_ai_commentary(
            current_price_usd=price_info["ounce_usd"],
            previous_price_usd=None,
            change_pct=price_info["change_percent"],
            toman_price=toman_price,
        )

        message = format_message(price_info, tether_info, coin_info, commentary)
        payload = build_telegram_payload(channel_id, message)
        send_telegram_message(bot_token, payload)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Sent: {message!r}")
    except Exception as e:
        sys.exit(f"Failed to post gold price: {e}")


def get_gold_price(api_key=None):
    headers = {}
    if api_key:
        headers["x-access-token"] = api_key
    response = requests.get(
        GOLD_API_URL,
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def parse_price(data):
    ounce_usd = data["price"]
    gram_24k_usd = data.get("price_gram_24k", ounce_usd / 31.1034768)
    change_percent = data.get("chp", data.get("change_percent", 0.0))
    return {
        "ounce_usd": ounce_usd,
        "gram_24k_usd": gram_24k_usd,
        "change_percent": change_percent,
    }


def get_iran_prices(api_key):
    response = requests.get(
        "https://Api.BrsApi.ir/Market/Gold_Currency.php",
        params={"key": api_key},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def parse_tether_price(data):
    for item in data.get("currency", []):
        if item.get("symbol") == "USDT_IRT":
            return {
                "toman": item["price"],
                "change_percent": item.get("change_percent", 0.0),
            }
    raise ValueError("USDT_IRT not found in brsapi.ir response")


def parse_gold_coin_price(data):
    for item in data.get("gold", []):
        if "امامی" in item.get("name", ""):
            return {
                "toman": item["price"],
                "change_percent": item.get("change_percent", 0.0),
            }
    return None


def is_significant_change(change_percent, threshold=SIGNIFICANT_CHANGE_THRESHOLD):
    return abs(change_percent) >= threshold


def calculate_18k_gold_toman(gram_24k_usd, tether_toman):
    gram_24k_toman = gram_24k_usd * tether_toman
    gram_18k_toman = gram_24k_toman * 0.75
    return gram_18k_toman


def get_ai_commentary(current_price_usd, previous_price_usd=None, change_pct=0.0, toman_price=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ""

    try:
        toman_info = f"، قیمت تومان: {toman_price}" if toman_price is not None else ""
        prompt = (
            f"قیمت فعلی طلا: {current_price_usd} دلار، "
            f"تغییرات: {change_pct}%{toman_info}.\n"
            "لطفاً فقط یک جمله کوتاه و طبیعی به زبان فارسی درباره تحلیل حرکت قیمت طلا بنویس. "
            "هیچ دیسکلایمر، هشدار عام یا مقدمهای ننویس و اعداد خام را دوباره تکرار نکن."
        )

        url = f"{GEMINI_API_URL}?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Warning: Gemini AI commentary unavailable: {e}")
        return ""


def format_message(price_info, tether_info=None, coin_info=None, commentary=""):
    arrow = "🔺" if price_info["change_percent"] >= 0 else "🔻"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    alerts = []
    if is_significant_change(price_info["change_percent"]):
        alerts.append("طلای جهانی")
    if tether_info is not None and is_significant_change(tether_info["change_percent"]):
        alerts.append("تتر")
    if coin_info is not None and is_significant_change(coin_info["change_percent"]):
        alerts.append("سکه امامی")

    lines = ["<b>🥇 قیمت لحظهای طلای جهانی</b>"]
    if alerts:
        lines.append(f"⚠️ نوسان قابلتوجه: {'، '.join(alerts)}")
    lines += [
        "",
        f"هر اونس: {price_info['ounce_usd']:.2f} دلار",
        f"هر گرم (۲۴ عیار): {price_info['gram_24k_usd']:.2f} دلار",
        f"تغییر: {arrow} {abs(price_info['change_percent']):.2f}%",
    ]

    if commentary:
        lines += ["", f"💡 {commentary}"]

    if tether_info is not None:
        tether_arrow = "🔺" if tether_info["change_percent"] >= 0 else "🔻"
        gold_18k_toman = calculate_18k_gold_toman(price_info["gram_24k_usd"], tether_info["toman"])
        lines += [
            "",
            f"💵 تتر (USDT): {tether_info['toman']:,} تومان",
            f"تغییر: {tether_arrow} {abs(tether_info['change_percent']):.2f}%",
            "",
            f"🥇 طلای ۱۸ عیار: {gold_18k_toman:,.0f} تومان",
        ]

    if coin_info is not None:
        coin_arrow = "🔺" if coin_info["change_percent"] >= 0 else "🔻"
        lines += [
            "",
            f"🟡 سکه امامی: {coin_info['toman']:,} تومان",
            f"تغییر: {coin_arrow} {abs(coin_info['change_percent']):.2f}%",
        ]

    lines += ["", f"🕒 بروزرسانی: {now}"]
    return "\n".join(lines)


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
