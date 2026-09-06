import os
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import MagicMock, patch
from project import (
    build_telegram_payload,
    calculate_18k_gold_toman,
    calculate_24h_change,
    format_message,
    get_ai_commentary,
    is_significant_change,
    load_price_history,
    parse_gold_coin_price,
    parse_price,
    parse_tether_price,
    record_price_history,
    save_price_history,
)



def test_parse_price_goldapi_io():
    data = {
        "price": 2650.4,
        "price_gram_24k": 85.2,
        "chp": -0.58,
    }
    parsed = parse_price(data)
    assert parsed["ounce_usd"] == 2650.4
    assert parsed["gram_24k_usd"] == 85.2
    assert parsed["change_percent"] == -0.58


def test_parse_price_gold_api_com():
    data = {
        "price": 3110.34768,
    }
    parsed = parse_price(data)
    assert parsed["ounce_usd"] == 3110.34768
    assert round(parsed["gram_24k_usd"], 2) == 100.0
    assert parsed["change_percent"] == 0.0


def test_parse_tether_price():
    data = {
        "currency": [
            {"symbol": "USD_IRT", "price": 59000, "change_percent": 0.1},
            {"symbol": "USDT_IRT", "price": 60000, "change_percent": 0.5},
        ]
    }
    res = parse_tether_price(data)
    assert res["toman"] == 60000
    assert res["change_percent"] == 0.5


def test_parse_tether_price_not_found():
    data = {"currency": []}
    with pytest.raises(ValueError):
        parse_tether_price(data)


def test_parse_gold_coin_price():
    data = {
        "gold": [
            {"name": "سکه تمام بهار آزادی طرح جدید (امامی)", "price": 45000000, "change_percent": 2.5},
        ]
    }
    res = parse_gold_coin_price(data)
    assert res["toman"] == 45000000
    assert res["change_percent"] == 2.5


def test_parse_gold_coin_price_not_found():
    data = {"gold": []}
    assert parse_gold_coin_price(data) is None


def test_is_significant_change():
    assert is_significant_change(2.5, threshold=2.0) is True
    assert is_significant_change(-2.0, threshold=2.0) is True
    assert is_significant_change(1.9, threshold=2.0) is False


def test_calculate_18k_gold_toman():
    res = calculate_18k_gold_toman(100.0, 60000)
    assert res == 4500000.0


def test_format_message_full():
    price_info = {"ounce_usd": 2700.0, "gram_24k_usd": 86.8, "change_percent": 2.5}
    tether_info = {"toman": 60000, "change_percent": 0.5}
    coin_info = {"toman": 45000000, "change_percent": 3.0}
    commentary = "بازار طلا صعودی است."

    message = format_message(price_info, tether_info, coin_info, commentary)

    assert "⚠️ نوسان" in message
    assert "2700.00" in message
    assert "💡 بازار طلا صعودی است." in message
    assert "USDT" in message
    assert "سکه امامی" in message


def test_build_telegram_payload():
    payload = build_telegram_payload("@my_channel", "hello")
    assert payload == {
        "chat_id": "@my_channel",
        "text": "hello",
        "parse_mode": "HTML",
    }


def test_get_ai_commentary_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_gemini_key")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "قیمت جهانی طلا به روند افزایشی خود ادامه میدهد."}
                    ]
                }
            }
        ]
    }
    with patch("requests.post", return_value=mock_response) as mock_post:
        commentary = get_ai_commentary(
            current_price_usd=2700.0,
            previous_price_usd=2650.0,
            change_pct=1.88,
            toman_price=60000,
        )
        assert commentary == "قیمت جهانی طلا به روند افزایشی خود ادامه میدهد."
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "key=fake_gemini_key" in args[0]
        assert kwargs["timeout"] == 10


def test_get_ai_commentary_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    commentary = get_ai_commentary(2700.0, 2650.0, 1.88)
    assert commentary == ""


def test_get_ai_commentary_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_gemini_key")
    with patch("requests.post", side_effect=Exception("Timeout or API Error")):
        commentary = get_ai_commentary(2700.0, 2650.0, 1.88)
        assert commentary == ""


def test_history_load_and_save(tmp_path):
    history_file = os.path.join(tmp_path, "test_history.json")
    assert load_price_history(history_file) == []

    data = [{"timestamp": 1700000000.0, "price_usd": 2000.0}]
    save_price_history(data, history_file)
    loaded = load_price_history(history_file)
    assert loaded == data


def test_record_price_history(tmp_path):
    history_file = os.path.join(tmp_path, "test_history.json")
    record_price_history(2500.0, timestamp="2026-09-05T10:00:00+00:00", filepath=history_file)
    history = load_price_history(history_file)
    assert len(history) == 1
    assert history[0]["price_usd"] == 2500.0
    assert history[0]["timestamp"] == "2026-09-05T10:00:00+00:00"


def test_calculate_24h_change_empty_or_insufficient():
    # Empty history
    assert calculate_24h_change(2600.0, []) == 0.0

    # Insufficient history (< 12 hours)
    now_ts = 1750000000.0
    recent_history = [{"timestamp": now_ts - 7200, "price_usd": 2500.0}]
    assert calculate_24h_change(2600.0, recent_history, current_timestamp=now_ts) == 0.0


def test_calculate_24h_change_sufficient_history():
    now_ts = 1750000000.0
    target_history = [
        {"timestamp": now_ts - 86400, "price_usd": 2500.0},
        {"timestamp": now_ts - 43200, "price_usd": 2550.0},
    ]
    # Current price 2600, 24h ago was 2500 -> ((2600 - 2500)/2500)*100 = 4.0%
    change = calculate_24h_change(2600.0, target_history, current_timestamp=now_ts)
    assert change == 4.0


def test_calculate_24h_change_iso_timestamps():
    now_dt = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    ts_24h_ago = (now_dt - timedelta(hours=24)).isoformat()
    history = [{"timestamp": ts_24h_ago, "price_usd": 2000.0}]
    change = calculate_24h_change(2100.0, history, current_timestamp=now_dt)
    assert change == 5.0


def test_parse_price_with_history():
    data = {"price": 2600.0}
    now_ts = 1750000000.0
    history = [{"timestamp": now_ts - 86400, "price_usd": 2500.0}]
    with patch("project.calculate_24h_change", return_value=4.0) as mock_calc:
        parsed = parse_price(data, history=history)
        assert parsed["change_percent"] == 4.0
        mock_calc.assert_called_once_with(2600.0, history)


def test_get_ai_commentary_expanded_market_data(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_gemini_key")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "افزایش همزمان طلای جهانی و تتر موجب رشد سکه امامی شد."}
                    ]
                }
            }
        ]
    }
    with patch("requests.post", return_value=mock_response) as mock_post:
        commentary = get_ai_commentary(
            current_price_usd=2700.0,
            change_pct=2.0,
            tether_info={"toman": 60000, "change_percent": 1.5},
            coin_info={"toman": 45000000, "change_percent": 3.0},
        )
        assert commentary == "افزایش همزمان طلای جهانی و تتر موجب رشد سکه امامی شد."
        payload = mock_post.call_args[1]["json"]
        prompt_text = payload["contents"][0]["parts"][0]["text"]
        assert "2700.0" in prompt_text
        assert "60,000" in prompt_text
        assert "45,000,000" in prompt_text
        assert "تغییرات ۲۴ ساعته: 2.0%" in prompt_text



