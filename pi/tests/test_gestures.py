from receiver.gestures import Command, DebounceConfig, DebounceState, Gesture, step

CFG = DebounceConfig(min_score=0.8, min_frames=3, cooldown_s=1.0, release_frames=3)


def run(frames, config=CFG):
    """(label, score, ts) 목록을 차례로 넣고 나온 명령만 모은다."""
    state, out = DebounceState(), []
    for label, score, ts in frames:
        state, cmd = step(state, Gesture(label, score, ts), config)
        if cmd is not None:
            out.append((cmd, ts))
    return out


def test_fires_after_min_frames():
    frames = [("five", 0.9, 0.0), ("five", 0.9, 0.1), ("five", 0.9, 0.2)]
    assert run(frames) == [(Command.PAUSE, 0.2)]


def test_ok_plays():
    frames = [("ok", 0.9, 0.0), ("ok", 0.9, 0.1), ("ok", 0.9, 0.2)]
    assert run(frames) == [(Command.PLAY, 0.2)]


def test_too_few_frames_does_nothing():
    assert run([("five", 0.9, 0.0), ("five", 0.9, 0.1)]) == []


def test_holding_fires_only_once():
    frames = [("like", 0.9, i * 0.1) for i in range(30)]
    assert run(frames) == [(Command.VOLUME_UP, 0.2)]


def test_low_score_frames_are_ignored():
    frames = [("five", 0.5, i * 0.1) for i in range(10)]
    assert run(frames) == []


def test_low_score_frame_breaks_the_streak():
    frames = [("five", 0.9, 0.0), ("five", 0.9, 0.1), ("five", 0.3, 0.2), ("five", 0.9, 0.3)]
    assert run(frames) == []


def test_unmapped_labels_never_fire():
    for label in ("no_hand", "no_gesture", "call", "three", "four"):
        assert run([(label, 0.99, i * 0.1) for i in range(10)]) == []


def test_release_and_repeat_fires_again_after_cooldown():
    frames = (
        [("one", 0.9, t) for t in (0.0, 0.1, 0.2)]
        + [("no_hand", 0.9, t) for t in (0.5, 0.6, 0.7)]
        + [("one", 0.9, t) for t in (1.3, 1.4, 1.5)]
    )
    assert run(frames) == [(Command.NEXT, 0.2), (Command.NEXT, 1.5)]


def test_flicker_during_hold_does_not_fire_again():
    # 실제 보드에서 본 현상: 한 번 들고 있는 동안 1~2프레임 다른 라벨/낮은 점수가 끼어든다
    frames = (
        [("two", 0.95, t) for t in (0.0, 0.2, 0.4, 0.6)]
        + [("no_gesture", 0.9, 0.8)]
        + [("two", 0.95, t) for t in (1.0, 1.2, 1.4, 1.6)]
        + [("two", 0.5, 1.8), ("two", 0.4, 2.0)]
        + [("two", 0.95, t) for t in (2.2, 2.4, 2.6, 2.8)]
    )
    assert run(frames) == [(Command.PREV, 0.4)]


def test_switching_to_other_gesture_fires_immediately():
    frames = [("five", 0.95, t) for t in (0.0, 0.2, 0.4)] + [("ok", 0.95, t) for t in (1.4, 1.6, 1.8)]
    assert run(frames) == [(Command.PAUSE, 0.4), (Command.PLAY, 1.8)]


def test_cooldown_delays_next_command_until_it_passes():
    frames = (
        [("one", 0.9, t) for t in (0.0, 0.1, 0.2)]
        + [("two", 0.9, t) for t in (0.3, 0.4, 0.5, 0.9, 1.2)]
    )
    assert run(frames) == [(Command.NEXT, 0.2), (Command.PREV, 1.2)]
