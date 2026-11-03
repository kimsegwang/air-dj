import json

from fakes import FakeRepository, FakeSink
from receiver.gestures import Command, DebounceConfig
from receiver.service import Receiver
from receiver.storage import CommandRecord, GestureBatcher, SafeRepository


def msg(label, score=0.95):
    return json.dumps({"seq": 0, "label": label, "score": score, "det": 0.9, "ms": 185}).encode()


def make(fail=False):
    player, repo = FakeSink(), FakeRepository(fail=fail)
    receiver = Receiver(player, SafeRepository(repo), DebounceConfig(min_frames=3, cooldown_s=1.0, release_frames=3),
                        batcher=GestureBatcher(interval_s=5.0))
    return receiver, player, repo


def test_three_frames_of_five_pause_and_save_command():
    receiver, player, repo = make()
    out = [receiver.handle(msg("five"), t) for t in (0.0, 0.2, 0.4)]
    assert out == [None, None, Command.PAUSE]
    assert player.commands == [Command.PAUSE]
    assert repo.commands == [CommandRecord("pause", "five", 0.4)]


def test_no_hand_breaks_hold_and_is_not_stored():
    receiver, player, repo = make()
    for t in (0.0, 0.2, 0.4):
        receiver.handle(msg("ok"), t)
    for t in (0.6, 0.8, 1.0):
        receiver.handle(msg("no_hand", 1.0), t)
    for t in (2.0, 2.2, 2.4):
        receiver.handle(msg("ok"), t)
    assert player.commands == [Command.PLAY, Command.PLAY]
    receiver.flush()
    stored = [r.label for batch in repo.gesture_batches for r in batch]
    assert "no_hand" not in stored and stored.count("ok") == 6


def test_gestures_saved_in_batches():
    receiver, _, repo = make()
    for t in (0.0, 1.0, 2.0, 5.0):
        receiver.handle(msg("three"), t)
    assert len(repo.gesture_batches) == 1 and len(repo.gesture_batches[0]) == 4


def test_bad_message_is_ignored():
    receiver, player, _ = make()
    assert receiver.handle(b"garbage", 0.0) is None
    assert player.commands == []


def test_storage_failure_does_not_stop_commands():
    receiver, player, _ = make(fail=True)
    for t in (0.0, 0.2, 0.4):
        receiver.handle(msg("like"), t)
    for t in (5.0, 5.2, 5.4):  # 일괄 저장도 실패하는 시점
        receiver.handle(msg("no_hand", 1.0), t - 0.1)
        receiver.handle(msg("dislike"), t)
    assert Command.VOLUME_UP in player.commands
