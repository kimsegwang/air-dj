import pytest

from receiver.storage import CommandRecord, GestureRecord
from receiver.supabase import SupabaseRepository, to_iso

KEY = "sb_secret_test_only"


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, status_code=201, text=""):
        self.calls = []
        self.status_code = status_code
        self.text = text

    def post(self, url, json, headers, timeout):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse(self.status_code, self.text)


def test_to_iso_is_utc():
    assert to_iso(0.0) == "1970-01-01T00:00:00+00:00"


def test_save_command_posts_one_row_with_apikey_header_only():
    session = FakeSession()
    repo = SupabaseRepository("https://abc.supabase.co/", KEY, session=session)
    repo.save_command(CommandRecord("pause", "five", 0.0))
    (call,) = session.calls
    assert call["url"] == "https://abc.supabase.co/rest/v1/gesture_commands"
    assert call["json"] == [{"received_at": "1970-01-01T00:00:00+00:00", "command": "pause", "label": "five"}]
    assert call["headers"]["apikey"] == KEY
    assert "Authorization" not in call["headers"]  # 새 키는 JWT가 아님
    assert call["headers"]["Prefer"] == "return=minimal"


def test_save_gestures_is_one_bulk_insert():
    session = FakeSession()
    repo = SupabaseRepository("https://abc.supabase.co", KEY, session=session)
    repo.save_gestures([GestureRecord("ok", 0.9, 0.0), GestureRecord("one", 1.0, 1.0)])
    (call,) = session.calls
    assert call["url"].endswith("/rest/v1/gesture_frames")
    assert [r["label"] for r in call["json"]] == ["ok", "one"]


def test_http_error_raises_without_leaking_key():
    session = FakeSession(status_code=401, text='{"message":"Invalid API key"}')
    repo = SupabaseRepository("https://abc.supabase.co", KEY, session=session)
    with pytest.raises(RuntimeError) as e:
        repo.save_command(CommandRecord("play", "ok", 0.0))
    assert "401" in str(e.value) and KEY not in str(e.value)
