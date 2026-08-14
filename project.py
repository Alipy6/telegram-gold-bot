import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

# .env رو نسبت به مسیر خودِ فایل project.py بارگذاری می‌کنیم (نه نسبت به پوشه‌ای
# که ازش اجرا شده). اگه .env پیدا نشه (مثلاً روی GitHub Actions که secrets رو
# مستقیم به‌عنوان environment variable تزریق می‌کنه)، این خط بی‌خطر رد می‌شه.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GOLD_API_URL = "https://api.gold-api.com/price/XAU/USD"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# gold-api.com فقط قیمت هر اونس رو می‌ده (برخلاف GoldAPI.io قبلی که مستقیم
# قیمت هر گرم رو هم برمی‌گردوند)، پس خودمون از روی این ثابت تبدیلش می‌کنیم.
GRAMS_PER_TROY_OUNCE = 31.1034768

# اگه درصد تغییرِ روزانه‌ی تتر یا سکه از این مقدار بیشتر بشه، یک هشدار نوسان
# بالای پیام اضافه می‌شه. (قیمت طلای جهانی از gold-api.com اصلاً درصد تغییر
# روزانه نمی‌ده، پس دیگه توی این هشدار حساب نمی‌شه - پایین‌تر توضیح داده شده.)
SIGNIFICANT_CHANGE_THRESHOLD = 2.0


def main():
    """
    یک چرخه‌ی کامل رو اجرا می‌کنه (گرفتن قیمت، ساخت پیام، ارسال) و بعد تموم می‌شه.
    تکرار هر ۳۰ دقیقه دیگه مسئولیت خودِ این فایل نیست - به یک زمان‌بند بیرونی
    (GitHub Actions یا Windows Task Scheduler) سپرده شده که این اسکریپت رو
    هر ۳۰ دقیقه یک‌بار صدا می‌زنه.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    brsapi_key = os.getenv("BRSAPI_KEY")  # اختیاریه؛ فقط برای قیمت تتر و سکه لازمه

    if not all([bot_token, channel_id]):
        sys.exit(
            "Missing one of TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID "
            "(check your .env file locally, or your repo secrets on GitHub Actions)."
        )

    try:
        data = get_gold_price()
        price_info = parse_price(data)

        # گرفتن قیمت‌های ایرانی عمداً "بهترین تلاش" (best-effort) است: اگه کلید
        # نداریم یا brsapi.ir قطع/در حال آپدیت بود، فقط از این بخش رد می‌شیم و
        # پیام طلا رو بدون این خط‌ها می‌فرستیم - یک مشکل جانبی نباید کل پست رو
        # متوقف کنه. تتر و سکه هم مستقل از هم پردازش می‌شن: اگه یکی‌شون توی
        # پاسخ brsapi.ir پیدا نشه (مثلاً ValueError)، اون‌یکی همچنان کار می‌کنه.
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

        message = format_message(price_info, tether_info, coin_info)
        payload = build_telegram_payload(channel_id, message)
        send_telegram_message(bot_token, payload)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Sent: {message!r}")
    except Exception as e:
        # exit code غیرصفر باعث می‌شه GitHub Actions اجرا رو "failed" علامت بزنه
        sys.exit(f"Failed to post gold price: {e}")


def get_gold_price():
    """
    قیمت لحظه‌ای طلا رو از gold-api.com می‌گیره — رایگان، بدون کلید، و بدون
    محدودیت نرخ درخواست (برخلاف GoldAPI.io که سهمیه‌ی رایگان ماهانه‌ش تموم شد).
    خروجی: دیکشنری خام JSON که سرور برگردونده.
    """
    response = requests.get(GOLD_API_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def parse_price(data):
    """
    از پاسخ خام gold-api.com فقط فیلدهایی که برای پیام لازم داریم رو استخراج می‌کنه.
    این تابع خالص (pure) است: هیچ درخواست شبکه‌ای نمی‌زنه، فقط یک دیکشنری پردازش می‌کنه.
    ورودی نمونه:
        {"currency": "USD", "price": 4165.2, "symbol": "XAU", "updatedAt": "...", ...}

    نکته: برخلاف GoldAPI.io قبلی، این سرویس قیمت هر گرم یا درصد تغییر روزانه رو
    مستقیم نمی‌ده - فقط قیمت هر اونس. قیمت هر گرم (۲۴ عیار) رو خودمون حساب
    می‌کنیم؛ درصد تغییر روزانه هم دیگه نداریم (برای همین توی پیام و هشدارها
    فقط برای تتر/سکه نمایش داده می‌شه، نه برای طلای جهانی).
    """
    ounce_usd = data["price"]
    return {
        "ounce_usd": ounce_usd,
        "gram_24k_usd": ounce_usd / GRAMS_PER_TROY_OUNCE,
    }


def get_iran_prices(api_key):
    """
    قیمت‌های داخلی (طلا، ارز، رمزارز به تومن) رو از brsapi.ir می‌گیره.
    خروجی: دیکشنری خام JSON با سه کلید gold/currency/cryptocurrency.

    نکته: brsapi.ir درخواست‌هایی با User-Agent پیش‌فرض کتابخونه‌های پایتون/Go رو
    خودکار مسدود می‌کنه (حتی تا ۲ ساعت مسدودی IP)، پس عمداً یک User-Agent شبیه
    مرورگر واقعی می‌فرستیم تا این اتفاق نیفته.
    """
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
    """
    از پاسخ brsapi.ir فقط قیمت تتر (USDT) به تومن رو استخراج می‌کنه؛ داخل
    لیست data["currency"] دنبال آیتمی با symbol == "USDT_IRT" می‌گرده.
    این تابع خالص (pure) است: هیچ درخواست شبکه‌ای نمی‌زنه.
    """
    for item in data["currency"]:
        if item["symbol"] == "USDT_IRT":
            return {
                "toman": item["price"],
                "change_percent": item["change_percent"],
            }
    raise ValueError("USDT_IRT not found in brsapi.ir response")


def parse_gold_coin_price(data):
    """
    قیمت سکه امامی رو از پاسخ brsapi.ir استخراج می‌کنه؛ داخل لیست data["gold"]
    دنبال آیتمی می‌گرده که کلمه‌ی "امامی" توی فیلد name اش باشه.

    نکته: brsapi.ir برخلاف currency (که symbol ثابت USDT_IRT داره)، مستندات
    رسمی‌ای برای symbol دقیق سکه امامی منتشر نکرده؛ به همین خاطر عمداً بر پایه‌ی
    نام فارسی (که در توضیحات API دیده شده) جستجو می‌کنه - این روش نسبت به تغییر
    احتمالی symbol مقاوم‌تره. اگه پیدا نشه (مثلاً fallback به None به‌جای raise)
    None برمی‌گردونه، دقیقاً مثل رفتار best-effort تتر توی main().

    این تابع خالص (pure) است: هیچ درخواست شبکه‌ای نمی‌زنه.
    """
    for item in data.get("gold", []):
        if "امامی" in item.get("name", ""):
            return {
                "toman": item["price"],
                "change_percent": item.get("change_percent", 0),
            }
    return None


def is_significant_change(change_percent, threshold=SIGNIFICANT_CHANGE_THRESHOLD):
    """
    آیا اندازه‌ی (قدرمطلق) درصد تغییر از آستانه‌ی مشخص‌شده بیشتره؟
    این تابع خالص (pure) است.
    """
    return abs(change_percent) >= threshold


def calculate_18k_gold_toman(gram_24k_usd, tether_toman):
    """
    قیمت هر گرم طلای ۱۸ عیار رو به تومان حساب می‌کنه؛ از قیمت گرم ۲۴ عیار (دلار،
    که خودِ GoldAPI.io مستقیم می‌ده) و نرخ تتر به تومان استفاده می‌کنه.
    این تابع خالص (pure) است: هیچ درخواست شبکه‌ای نمی‌زنه، فقط دو عدد رو پردازش می‌کنه.

    نکته: این معادل «جهانی» قیمت ۱۸ عیاره، نه لزوماً قیمت دقیق بازار طلافروشی
    ایران (که معمولاً اجرت، سود و مالیات هم روش اضافه می‌شه).
    """
    gram_24k_toman = gram_24k_usd * tether_toman
    gram_18k_toman = gram_24k_toman * 0.75
    return gram_18k_toman


def format_message(price_info, tether_info=None, coin_info=None):
    """
    یک پیام فارسیِ خوانا برای تلگرام از روی اطلاعات قیمت می‌سازه (تابع خالص، قابل تست).
    tether_info و coin_info اختیاری‌ان: هر کدوم داده بشن، یک بخش اضافه برای اون
    قیمت به پیام اضافه می‌شه. اگه تغییر روزانه‌ی تتر یا سکه از
    SIGNIFICANT_CHANGE_THRESHOLD بیشتر باشه، یک بنر هشدار بالای پیام اضافه می‌شه
    (طلای جهانی توی این هشدار حساب نمی‌شه، چون gold-api.com درصد تغییر روزانه نمی‌ده).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    alerts = []
    if tether_info is not None and is_significant_change(tether_info["change_percent"]):
        alerts.append("تتر")
    if coin_info is not None and is_significant_change(coin_info["change_percent"]):
        alerts.append("سکه امامی")

    lines = ["<b>🥇 قیمت لحظه‌ای طلای جهانی</b>"]
    if alerts:
        lines.append(f"⚠️ نوسان قابل‌توجه: {'، '.join(alerts)}")
    lines += [
        "",
        f"هر اونس: {price_info['ounce_usd']:.2f} دلار",
        f"هر گرم (۲۴ عیار): {price_info['gram_24k_usd']:.2f} دلار",
    ]

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
    """payload لازم برای فراخوانی sendMessage تلگرام رو می‌سازه (تابع خالص، قابل تست)."""
    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }


def send_telegram_message(bot_token, payload):
    """پیام رو با فراخوانی واقعی Telegram Bot API ارسال می‌کنه."""
    url = TELEGRAM_API_URL.format(token=bot_token)
    response = requests.post(url, data=payload, timeout=10)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    main()
