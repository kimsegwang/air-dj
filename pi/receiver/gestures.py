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


@dataclass(frozen=True)
class DebounceState:
    label: str | None = None
    count: int = 0
    fired: bool = False  # 현재 유지 중인 제스처로 이미 명령을 냈는지
    last_fire_ts: float | None = None


def step(
    state: DebounceState,
    gesture: Gesture,
    config: DebounceConfig = DebounceConfig(),
    mapping: dict[str, Command] = DEFAULT_MAPPING,
) -> tuple[DebounceState, Command | None]:
    """프레임 하나를 반영한 새 상태와, 낼 명령(없으면 None)을 돌려준다.

    같은 제스처를 계속 유지해도 명령은 한 번만 나간다. 다른 라벨(또는 낮은 점수)이
    끼어들어야 다시 낼 수 있다.
    """
    label = gesture.label if gesture.score >= config.min_score else None

    if label != state.label:
        state = DebounceState(label=label, count=0, last_fire_ts=state.last_fire_ts)
    if label is None:
        return state, None
    state = replace(state, count=state.count + 1)

    command = mapping.get(label)
    if command is None or state.fired or state.count < config.min_frames:
        return state, None
    if state.last_fire_ts is not None and gesture.ts - state.last_fire_ts < config.cooldown_s:
        return state, None
    return replace(state, fired=True, last_fire_ts=gesture.ts), command
