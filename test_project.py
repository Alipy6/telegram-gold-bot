from project import build_telegram_payload, format_message, parse_price


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
