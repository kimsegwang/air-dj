"""제스처 → 명령 변환 (순수 함수).

라벨은 espressif/hand_gesture_recognition 0.2.1의 hand_gesture_cat_names 기준:
one, two, three, four, five, like, ok, no_gesture, call, dislike, no_hand
"""

from dataclasses import dataclass, replace
from enum import Enum


class Command(str, Enum):
    PLAY = "play"
    PAUSE = "pause"
    NEXT = "next"
    PREV = "prev"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"


DEFAULT_MAPPING: dict[str, Command] = {
    "ok": Command.PLAY,
    "five": Command.PAUSE,  # 모델에 fist 라벨이 없어서 손바닥을 정지로 쓴다
    "one": Command.NEXT,
    "two": Command.PREV,
    "like": Command.VOLUME_UP,
    "dislike": Command.VOLUME_DOWN,
}


@dataclass(frozen=True)
class Gesture:
    label: str
    score: float
    ts: float  # 초 단위 (수신 시각)


@dataclass(frozen=True)
class DebounceConfig:
    min_score: float = 0.8   # 이보다 낮은 프레임은 "손 없음"으로 취급
    min_frames: int = 3      # 같은 라벨이 연속으로 이만큼 나와야 명령
    cooldown_s: float = 1.0  # 명령 사이 최소 간격
    release_frames: int = 5  # 명령을 낸 라벨이 연속으로 이만큼(약 1초) 안 보여야 "내렸다"로 본다


@dataclass(frozen=True)
class DebounceState:
    label: str | None = None
    count: int = 0
    fired_label: str | None = None  # 마지막으로 명령을 낸 라벨 (아직 안 내렸으면 유지)
    away: int = 0                   # fired_label이 연속으로 안 보인 프레임 수
    last_fire_ts: float | None = None


def step(
    state: DebounceState,
    gesture: Gesture,
    config: DebounceConfig = DebounceConfig(),
    mapping: dict[str, Command] = DEFAULT_MAPPING,
) -> tuple[DebounceState, Command | None]:
    """프레임 하나를 반영한 새 상태와, 낼 명령(없으면 None)을 돌려준다.

    같은 제스처를 계속 유지해도 명령은 한 번만 나간다. 같은 명령을 다시 내려면 그 제스처가
    release_frames 동안 연속으로 안 보여야 한다 (들고 있는 중 1~2프레임 깜빡임은 무시).
    다른 제스처로 바꾸면 바로 반응한다.
    """
    label = gesture.label if gesture.score >= config.min_score else None

    if state.fired_label is not None:
        away = 0 if label == state.fired_label else state.away + 1
        if away >= config.release_frames:
            state = replace(state, fired_label=None, away=0)
        else:
            state = replace(state, away=away)

    if label != state.label:
        state = replace(state, label=label, count=0)
    if label is None:
        return state, None
    state = replace(state, count=state.count + 1)

    command = mapping.get(label)
    if command is None or label == state.fired_label or state.count < config.min_frames:
        return state, None
    if state.last_fire_ts is not None and gesture.ts - state.last_fire_ts < config.cooldown_s:
        return state, None
    return replace(state, fired_label=label, away=0, last_fire_ts=gesture.ts), command
