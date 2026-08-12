from project import build_telegram_payload, format_message, parse_price, parse_tether_price

# نمونه‌ی واقعی (خلاصه‌شده) از پاسخ brsapi.ir که برای ساخت این تست‌ها استفاده شده
BRSAPI_SAMPLE = {
    "currency": [
        {
            "symbol": "USDT_IRT",
            "name": "دلار تتر",
            "price": 81983,
            "change_percent": -1.02,
            "unit": "تومان",
        },
        {
            "symbol": "USD",
            "name": "دلار",
            "price": 81650,
            "change_percent": -0.91,
            "unit": "تومان",
        },
    ]
}


def test_parse_price():
    data = {
        "price": 2650.4,
        "price_gram_24k": 85.2,
        "chp": -0.58,
        "some_other_field": "ignored",
    }
    assert parse_price(data) == {
        "ounce_usd": 2650.4,
        "gram_24k_usd": 85.2,
        "change_percent": -0.58,
    }


def test_format_message_negative_change():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2, "change_percent": -0.58}
    message = format_message(price_info)
    assert "2650.40" in message
    assert "85.20" in message
    assert "🔻" in message
    assert "0.58%" in message


def test_format_message_positive_change():
    price_info = {"ounce_usd": 2700.0, "gram_24k_usd": 86.8, "change_percent": 1.2}
    message = format_message(price_info)
    assert "🔺" in message
    assert "1.20%" in message


def test_build_telegram_payload():
    payload = build_telegram_payload("@my_channel", "hello")
    assert payload == {
        "chat_id": "@my_channel",
        "text": "hello",
        "parse_mode": "HTML",
    }


def test_parse_tether_price():
    assert parse_tether_price(BRSAPI_SAMPLE) == {
        "toman": 81983,
        "change_percent": -1.02,
    }


def test_format_message_includes_tether_when_given():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2, "change_percent": -0.58}
    tether_info = {"toman": 81983, "change_percent": -1.02}
    message = format_message(price_info, tether_info)
    assert "تتر" in message
    assert "81,983" in message
    assert "🔻" in message


def test_format_message_omits_tether_when_not_given():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2, "change_percent": -0.58}
    message = format_message(price_info)
    assert "تتر" not in message
