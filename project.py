import json
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GOLD_API_URL = "https://api.gold-api.com/price/XAU"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent"

SIGNIFICANT_CHANGE_THRESHOLD = 2.0
HISTORY_FILE = os.path.join(BASE_DIR, "gold_price_history.json")


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
        history = load_price_history()
        data = get_gold_price(gold_api_key)
        price_info = parse_price(data, history=history)

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
            tether_info=tether_info,
            coin_info=coin_info,
        )

        record_price_history(price_info["ounce_usd"])

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


def parse_price(data, history=None):
    ounce_usd = data["price"]
    gram_24k_usd = data.get("price_gram_24k", ounce_usd / 31.1034768)

    if history is not None:
        change_percent = calculate_24h_change(ounce_usd, history)
    elif "chp" in data:
        change_percent = data["chp"]
    elif "change_percent" in data:
        change_percent = data["change_percent"]
    else:
        change_percent = 0.0

    return {
        "ounce_usd": ounce_usd,
        "gram_24k_usd": gram_24k_usd,
        "change_percent": change_percent,
    }


def _parse_timestamp(ts):
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return float(ts)
        except ValueError:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
    raise ValueError(f"Unsupported timestamp format: {ts}")


def load_price_history(filepath=HISTORY_FILE):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Warning: Could not read history file: {e}")
        return []


def save_price_history(history, filepath=HISTORY_FILE):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Warning: Could not write history file: {e}")


def calculate_24h_change(current_price_usd, history, current_timestamp=None):
    if not history or not isinstance(history, list):
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Info: Historical data not available yet.")
        return 0.0

    if current_timestamp is None:
        current_timestamp = datetime.now(timezone.utc).timestamp()
    elif isinstance(current_timestamp, datetime):
        if current_timestamp.tzinfo is None:
            current_timestamp = current_timestamp.replace(tzinfo=timezone.utc)
        current_timestamp = current_timestamp.timestamp()
    elif isinstance(current_timestamp, (int, float)):
        current_timestamp = float(current_timestamp)
    elif isinstance(current_timestamp, str):
        try:
            current_timestamp = _parse_timestamp(current_timestamp)
        except Exception:
            current_timestamp = datetime.now(timezone.utc).timestamp()

    valid_records = []
    for rec in history:
        if isinstance(rec, dict) and "price_usd" in rec and "timestamp" in rec:
            try:
                ts = _parse_timestamp(rec["timestamp"])
                price = float(rec["price_usd"])
                valid_records.append((ts, price))
            except (ValueError, TypeError):
                continue

    if not valid_records:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Info: No valid historical records found.")
        return 0.0

    target_ts = current_timestamp - 86400.0

    valid_records.sort(key=lambda x: x[0])
    oldest_ts, oldest_price = valid_records[0]

    if (oldest_ts - target_ts) > 43200.0:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Info: Historical data is not old enough yet.")
        return 0.0

    closest_ts, closest_price = min(valid_records, key=lambda x: abs(x[0] - target_ts))

    if closest_price == 0:
        return 0.0

    change_pct = ((current_price_usd - closest_price) / closest_price) * 100.0
    return round(change_pct, 2)


def record_price_history(current_price_usd, timestamp=None, filepath=HISTORY_FILE):
    history = load_price_history(filepath)
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    elif isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.isoformat()

    history.append({
        "timestamp": timestamp,
        "price_usd": current_price_usd,
    })
    save_price_history(history, filepath)



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


def get_ai_commentary(
    current_price_usd,
    previous_price_usd=None,
    change_pct=0.0,
    toman_price=None,
    tether_info=None,
    coin_info=None,
    tether_change_pct=None,
    coin_price=None,
    coin_change_pct=None,
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ""

    toman_val = toman_price
    tether_change_val = tether_change_pct
    if tether_info and isinstance(tether_info, dict):
        if toman_val is None:
            toman_val = tether_info.get("toman")
        if tether_change_val is None:
            tether_change_val = tether_info.get("change_percent")

    coin_val = coin_price
    coin_change_val = coin_change_pct
    if coin_info and isinstance(coin_info, dict):
        if coin_val is None:
            coin_val = coin_info.get("toman")
        if coin_change_val is None:
            coin_change_val = coin_info.get("change_percent")

    try:
        details = [f"قیمت انس طلای جهانی: {current_price_usd} دلار (تغییرات ۲۴ ساعته: {change_pct}%)"]

        if toman_val is not None:
            t_change_str = f" با تغییرات {tether_change_val}%" if tether_change_val is not None else ""
            details.append(f"نرخ تتر/تومان: {toman_val:,} تومان{t_change_str}")

        if coin_val is not None:
            c_change_str = f" با تغییرات {coin_change_val}%" if coin_change_val is not None else ""
            details.append(f"قیمت سکه امامی: {coin_val:,} تومان{c_change_str}")

        market_context = "\n".join(details)

        prompt = (
            f"اطلاعات بازار:\n{market_context}\n\n"
            "لطفاً یک تحلیل کوتاه، تحلیلی و طبیعی به زبان فارسی (در ۱ الی ۲ جمله) ارائه دهید "
            "که رابطه و اثر همزمان طلای جهانی، نرخ تتر/تومان و قیمت سکه امامی بر بازار داخلی را بررسی کند. "
            "از نوشتن دیسکلایمر، مقدمه، یا تکرار مستقیم اعداد خام خودداری کنید."
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
