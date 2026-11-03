from receiver.gestures import Gesture
from receiver.message import parse_gesture


def test_parses_esp32_payload():
    payload = b'{"seq":123,"label":"five","score":0.970,"det":0.880,"ms":185}'
    assert parse_gesture(payload, 1000.0) == Gesture("five", 0.97, 1000.0)


def test_no_hand_payload():
    payload = b'{"seq":1,"label":"no_hand","score":1.000,"det":0.000,"ms":190}'
    assert parse_gesture(payload, 5.0) == Gesture("no_hand", 1.0, 5.0)


def test_bad_payloads_return_none():
    for payload in (b"", b"not json", b"[]", b'{"label":"five"}', b'{"score":0.9}', b'{"label":"","score":1}',
                    b'{"label":5,"score":1}', b'{"label":"five","score":"x"}'):
        assert parse_gesture(payload, 0.0) is None, payload
