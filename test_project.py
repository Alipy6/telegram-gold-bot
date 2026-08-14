import pytest

from project import (
    build_telegram_payload,
    calculate_18k_gold_toman,
    format_message,
    is_significant_change,
    parse_gold_coin_price,
    parse_price,
    parse_tether_price,
)


# ---------- parse_price ----------

def test_parse_price():
    data = {
        "currency": "USD",
        "price": 4165.200195,
        "symbol": "XAU",
        "updatedAt": "2026-08-14T10:00:00Z",
    }
    result = parse_price(data)
    assert result["ounce_usd"] == 4165.200195
    assert result["gram_24k_usd"] == pytest.approx(133.914, abs=0.01)


# ---------- parse_tether_price ----------

def test_parse_tether_price_found():
    data = {
        "currency": [
            {"symbol": "USD_IRT", "price": 91000, "change_percent": 0.1},
            {"symbol": "USDT_IRT", "price": 95000, "change_percent": 0.3},
        ]
    }
    assert parse_tether_price(data) == {"toman": 95000, "change_percent": 0.3}


def test_parse_tether_price_not_found_raises():
    data = {"currency": [{"symbol": "USD_IRT", "price": 91000, "change_percent": 0.1}]}
    with pytest.raises(ValueError):
        parse_tether_price(data)


# ---------- parse_gold_coin_price ----------

def test_parse_gold_coin_price_found():
    data = {
        "gold": [
            {"name": "طلای 18 عیار", "price": 5000000, "change_percent": 0.4},
            {"name": "سکه امامی", "price": 45000000, "change_percent": 1.2},
        ]
    }
    assert parse_gold_coin_price(data) == {"toman": 45000000, "change_percent": 1.2}


def test_parse_gold_coin_price_not_found_returns_none():
    data = {"gold": [{"name": "طلای 18 عیار", "price": 5000000, "change_percent": 0.4}]}
    assert parse_gold_coin_price(data) is None


def test_parse_gold_coin_price_missing_key_returns_none():
    # اگه اصلاً کلید "gold" توی پاسخ نباشه، نباید کرش کنه
    assert parse_gold_coin_price({}) is None


# ---------- calculate_18k_gold_toman ----------

def test_calculate_18k_gold_toman():
    assert calculate_18k_gold_toman(85.2, 95000) == pytest.approx(6070500.0)


def test_calculate_18k_gold_toman_zero_rate():
    assert calculate_18k_gold_toman(85.2, 0) == 0


# ---------- is_significant_change ----------

def test_is_significant_change_above_threshold():
    assert is_significant_change(2.5) is True
    assert is_significant_change(-3.0) is True  # قدرمطلق، پس منفی هم حساب می‌شه


def test_is_significant_change_below_threshold():
    assert is_significant_change(1.0) is False
    assert is_significant_change(-1.9) is False


def test_is_significant_change_custom_threshold():
    assert is_significant_change(4.0, threshold=5.0) is False
    assert is_significant_change(6.0, threshold=5.0) is True


# ---------- format_message ----------

def test_format_message_gold_only():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2}
    message = format_message(price_info)
    assert "هر اونس: 2650.40 دلار" in message
    assert "تتر" not in message
    assert "سکه امامی" not in message
    assert "⚠️" not in message


def test_format_message_with_tether_includes_18k_line():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2}
    tether_info = {"toman": 95000, "change_percent": 0.3}
    message = format_message(price_info, tether_info)
    assert "تتر (USDT): 95,000 تومان" in message
    assert "طلای ۱۸ عیار" in message
    assert "سکه امامی" not in message


def test_format_message_with_coin():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2}
    coin_info = {"toman": 45000000, "change_percent": 1.0}
    message = format_message(price_info, coin_info=coin_info)
    assert "سکه امامی: 45,000,000 تومان" in message


def test_format_message_significant_tether_change_shows_alert():
    price_info = {"ounce_usd": 2650.4, "gram_24k_usd": 85.2}
    tether_info = {"toman": 95000, "change_percent": -2.4}
    message = format_message(price_info, tether_info)
    assert "⚠️ نوسان قابل‌توجه: تتر" in message


# ---------- build_telegram_payload ----------

def test_build_telegram_payload():
    payload = build_telegram_payload("@my_channel", "hello")
    assert payload == {
        "chat_id": "@my_channel",
        "text": "hello",
        "parse_mode": "HTML",
    }
