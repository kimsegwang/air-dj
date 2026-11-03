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


NO_HAND = "no_hand"


@dataclass(frozen=True)
class DebounceConfig:
    min_score: float = 0.8   # 이보다 낮은 프레임은 표로 세지 않는다
    window: int = 5          # 최근 이만큼의 프레임에서
    min_frames: int = 3      # 같은 제스처가 이만큼 나오면 명령 (사이에 no_gesture가 끼어도 된다)
    cooldown_s: float = 1.0  # 명령 사이 최소 간격
    release_frames: int = 5          # 손이 화면에서 사라진 채(no_hand) 이만큼(약 1초) 지나면 "내렸다"
    release_idle_frames: int = 25    # 손은 보이지만 그 제스처가 아닌 채 이만큼(약 5초) 지나도 "내렸다"


@dataclass(frozen=True)
class DebounceState:
    recent: tuple[str | None, ...] = ()  # 최근 window 프레임의 표 (명령 라벨이 아니거나 점수가 낮으면 None)
    fired_label: str | None = None       # 마지막으로 명령을 낸 라벨 (아직 안 내렸으면 유지)
    gone: int = 0                        # fired_label 이후 연속 no_hand 프레임 수
    since: int = 0                       # fired_label이 마지막으로 보인 뒤 지난 프레임 수
    last_fire_ts: float | None = None


def step(
    state: DebounceState,
    gesture: Gesture,
    config: DebounceConfig = DebounceConfig(),
    mapping: dict[str, Command] = DEFAULT_MAPPING,
) -> tuple[DebounceState, Command | None]:
    """프레임 하나를 반영한 새 상태와, 낼 명령(없으면 None)을 돌려준다.

    실측(2026-11-03): 제스처를 들고 있어도 no_gesture가 1~20프레임씩 섞여 나온다.
    그래서 "연속 N프레임"이 아니라 "최근 window 중 min_frames"로 센다.
    같은 제스처를 계속 유지해도 명령은 한 번만 나간다. 같은 명령을 다시 내려면 손을 화면 밖으로
    빼거나(release_frames), 오래 다른 손 모양을 해야 한다(release_idle_frames).
    다른 제스처로 바꾸면 바로 반응한다.
    """
    vote = gesture.label if gesture.label in mapping and gesture.score >= config.min_score else None

    if state.fired_label is not None:
        if vote == state.fired_label:
            state = replace(state, gone=0, since=0)
        else:
            gone = state.gone + 1 if gesture.label == NO_HAND else 0
            since = state.since + 1
            if gone >= config.release_frames or since >= config.release_idle_frames:
                state = replace(state, fired_label=None, gone=0, since=0)
            else:
                state = replace(state, gone=gone, since=since)

    state = replace(state, recent=(state.recent + (vote,))[-config.window:])
    if vote is None or vote == state.fired_label or state.recent.count(vote) < config.min_frames:
        return state, None
    if state.last_fire_ts is not None and gesture.ts - state.last_fire_ts < config.cooldown_s:
        return state, None
    return replace(state, recent=(), fired_label=vote, gone=0, since=0, last_fire_ts=gesture.ts), mapping[vote]
