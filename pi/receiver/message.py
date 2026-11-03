"""MQTT 페이로드 → Gesture (순수 함수).

ESP32 페이로드 형식 (CLAUDE.md "MQTT 메시지"):
    {"seq":123,"label":"five","score":0.970,"det":0.880,"ms":185}
ESP32에는 시계가 없으므로 ts는 수신 시각을 쓴다.
"""

import json

from receiver.gestures import Gesture


def parse_gesture(payload: bytes, received_at: float) -> Gesture | None:
    """형식이 틀리면 None (서비스는 무시하고 계속 돈다)."""
    try:
        data = json.loads(payload)
        label = data["label"]
        score = float(data["score"])
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(label, str) or not label:
        return None
    return Gesture(label=label, score=score, ts=received_at)
