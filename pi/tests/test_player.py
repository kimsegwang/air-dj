import json
import os
import socket
import tempfile
import threading

import pytest

from receiver.gestures import Command
from receiver.player import MPV_COMMANDS, MpvPlayer


def test_every_command_has_mpv_mapping():
    assert set(MPV_COMMANDS) == set(Command)


def test_read_reply_skips_events_and_other_ids():
    a, b = socket.socketpair()
    with a, b:
        b.sendall(b'{"event":"pause"}\n{"error":"success","request_id":6}\n'
                  b'{"error":"success","data":null,"request_id":7}\n')
        assert MpvPlayer._read_reply(a, 7) == {"error": "success", "data": None, "request_id": 7}


def test_unreachable_socket_returns_false():
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("AF_UNIX 없음 (Windows)")
    assert MpvPlayer("/nonexistent/mpvsocket", timeout_s=0.2).execute(Command.PAUSE) is False


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="AF_UNIX 없음 (Windows)")
def test_sends_json_line_to_fake_mpv():
    path = os.path.join(tempfile.mkdtemp(), "mpv.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)
    received = []

    def fake_mpv():
        conn, _ = server.accept()
        with conn:
            line = conn.makefile("rb").readline()
            req = json.loads(line)
            received.append(req)
            conn.sendall(b'{"event":"property-change"}\n')
            conn.sendall(json.dumps({"error": "success", "request_id": req["request_id"]}).encode() + b"\n")

    t = threading.Thread(target=fake_mpv)
    t.start()
    assert MpvPlayer(path).execute(Command.VOLUME_UP) is True
    t.join(timeout=2)
    server.close()
    assert received[0]["command"] == ["add", "volume", 10]
