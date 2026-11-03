"""대시보드에 보여 줄 상태. MQTT 스레드가 쓰고 대시보드 스레드가 읽는다."""

import json
import threading
import time
from collections import deque
from pathlib import PureWindowsPath

MPV_PROPS = ["metadata", "media-title", "filename", "time-pos", "duration", "pause", "volume",
             "playlist-pos", "playlist-count", "playlist"]
UPCOMING = 5

# 화면 표시용 평활화. pi/receiver/gestures.py DebounceConfig(window=5, min_score=0.8)와 맞춘다
SMOOTH_WINDOW = 5
SMOOTH_MIN_SCORE = 0.8
SMOOTH_SHOW_VOTES = 2  # 이만큼 나오면 그 제스처로 표시 (명령은 receiver 기준 3)
NOT_GESTURES = {"no_hand", "no_gesture"}


def smooth_gesture(frames: list[dict]) -> dict:
    """최근 프레임들 → 깜빡이지 않는 표시 상태 (순수 함수).

    state: "none"(프레임 없음) | "no_hand" | "hand"(손은 있지만 제스처 아님) | "gesture"
    """
    if not frames:
        return {"state": "none"}
    hands = [f for f in frames if f.get("label") != "no_hand"]
    if len(hands) * 2 < len(frames):
        return {"state": "no_hand"}
    votes: dict[str, list[dict]] = {}
    for f in hands:
        if f.get("label") not in NOT_GESTURES and (f.get("score") or 0) >= SMOOTH_MIN_SCORE:
            votes.setdefault(f["label"], []).append(f)
    det = max((f.get("det") or 0) for f in hands)
    if votes:
        label, picked = max(votes.items(), key=lambda kv: (len(kv[1]), kv[1][-1] is frames[-1]))
        if len(picked) >= SMOOTH_SHOW_VOTES:
            return {"state": "gesture", "label": label, "votes": len(picked), "window": len(frames),
                    "score": max(f["score"] for f in picked), "det": max((f.get("det") or 0) for f in picked)}
    return {"state": "hand", "det": det, "votes": max((len(v) for v in votes.values()), default=0),
            "window": len(frames)}


def track_name(filename: str) -> str:
    return PureWindowsPath(filename).stem


def now_playing(props: dict) -> dict:
    """mpv 속성 → 화면용 곡 정보 (순수 함수). mpv가 응답하지 않으면 props는 빈 dict."""
    meta = {str(k).lower(): v for k, v in (props.get("metadata") or {}).items()}  # 형식마다 키 대소문자가 다르다
    filename = props.get("filename")
    pos = props.get("playlist-pos")
    playlist = props.get("playlist") or []
    upcoming = []
    if isinstance(pos, int) and pos >= 0 and playlist:
        n = len(playlist)
        upcoming = [track_name(playlist[(pos + i) % n].get("filename", "")) for i in range(1, min(UPCOMING, n - 1) + 1)]
    return {
        "available": bool(props),
        "loaded": filename is not None,
        "title": meta.get("title") or (track_name(filename) if filename else props.get("media-title")),
        "artist": meta.get("artist") or meta.get("album_artist"),
        "album": meta.get("album"),
        "filename": filename,
        "position": props.get("time-pos"),
        "duration": props.get("duration"),
        "paused": props.get("pause"),
        "volume": props.get("volume"),
        "index": pos + 1 if isinstance(pos, int) and pos >= 0 else None,
        "count": props.get("playlist-count"),
        "upcoming": upcoming,
    }


class DashboardState:
    def __init__(self, max_commands: int = 12):
        self._lock = threading.Lock()
        self._gesture: dict | None = None
        self._gesture_at: float | None = None
        self._recent: deque = deque(maxlen=SMOOTH_WINDOW)
        self._commands: deque = deque(maxlen=max_commands)
        self.mqtt_connected = False

    def on_gesture(self, payload: bytes, now: float | None = None) -> None:
        try:
            data = json.loads(payload)
        except ValueError:
            return
        if isinstance(data, dict):
            with self._lock:
                self._gesture, self._gesture_at = data, now or time.time()
                self._recent.append(data)

    def on_command(self, command: str, label: str | None, ok: bool, now: float | None = None) -> None:
        with self._lock:
            self._commands.appendleft({"command": command, "label": label, "ok": ok, "at": now or time.time()})

    def snapshot(self, now: float | None = None) -> dict:
        now = now or time.time()
        with self._lock:
            gesture = dict(self._gesture) if self._gesture else None
            age = now - self._gesture_at if self._gesture_at else None
            commands = [dict(c, ago=now - c["at"]) for c in self._commands]
            smoothed = smooth_gesture(list(self._recent))
        return {"mqtt": self.mqtt_connected, "gesture": gesture, "gesture_age": age, "smoothed": smoothed,
                "commands": commands}
