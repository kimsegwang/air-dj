"""대시보드에 보여 줄 상태. MQTT 스레드가 쓰고 대시보드 스레드가 읽는다."""

import json
import threading
import time
from collections import deque
from pathlib import PureWindowsPath

MPV_PROPS = ["metadata", "media-title", "filename", "time-pos", "duration", "pause", "volume",
             "playlist-pos", "playlist-count", "playlist"]
UPCOMING = 5


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

    def on_command(self, command: str, label: str | None, ok: bool, now: float | None = None) -> None:
        with self._lock:
            self._commands.appendleft({"command": command, "label": label, "ok": ok, "at": now or time.time()})

    def snapshot(self, now: float | None = None) -> dict:
        now = now or time.time()
        with self._lock:
            gesture = dict(self._gesture) if self._gesture else None
            age = now - self._gesture_at if self._gesture_at else None
            commands = [dict(c, ago=now - c["at"]) for c in self._commands]
        return {"mqtt": self.mqtt_connected, "gesture": gesture, "gesture_age": age, "commands": commands}
