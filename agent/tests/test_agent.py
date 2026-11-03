import io

import pytest

from air_dj_agent.commands import MPV_COMMANDS, parse_command
from air_dj_agent.mpv import mpv_args, read_replies

# pi/receiver/gestures.py의 Command 값과 같아야 한다
COMMANDS = {"play", "pause", "next", "prev", "volume_up", "volume_down"}


def test_every_command_has_mpv_mapping():
    assert set(MPV_COMMANDS) == COMMANDS


def test_parse_command():
    assert parse_command(b'{"command":"pause","label":"five","ts":1793679259.65}') == ("pause", "five")
    assert parse_command(b'{"command":"next"}') == ("next", None)


def test_parse_rejects_bad_payloads():
    for payload in (b"garbage", b"{}", b'{"command":"rm -rf"}', b'{"command":1}', b"[]"):
        assert parse_command(payload) is None


def test_read_replies_skips_events_and_other_ids():
    stream = io.BytesIO(b'{"event":"pause"}\n{"error":"success","request_id":6}\n'
                        b'{"error":"success","data":null,"request_id":7}\n'
                        b'{"error":"property unavailable","request_id":8}\n')
    replies = read_replies(stream.read, {7, 8})
    assert replies[7] == {"error": "success", "data": None, "request_id": 7}
    assert replies[8]["error"] == "property unavailable"


def test_read_replies_raises_when_closed():
    with pytest.raises(OSError):
        read_replies(io.BytesIO(b'{"error":"success","request_id":1}\n').read, {1, 2})


def test_mpv_args_ipc_and_music_dir():
    args = mpv_args("mpv", r"\\.\pipe\x", r"C:\music")
    assert args[0] == "mpv" and args[-1] == r"C:\music"
    assert r"--input-ipc-server=\\.\pipe\x" in args


def test_mpv_args_without_music_dir_starts_empty():
    args = mpv_args("mpv", r"\\.\pipe\x", None)
    assert args[-1].startswith("--") and "--idle=yes" in args
