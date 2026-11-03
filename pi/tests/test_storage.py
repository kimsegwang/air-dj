from receiver.storage import CommandRecord, GestureBatcher, GestureRecord, SafeRepository


class FakeRepository:
    def __init__(self, fail=False):
        self.fail = fail
        self.commands = []
        self.gesture_batches = []

    def save_command(self, record):
        if self.fail:
            raise ConnectionError("db down")
        self.commands.append(record)

    def save_gestures(self, records):
        if self.fail:
            raise ConnectionError("db down")
        self.gesture_batches.append(list(records))


def g(ts):
    return GestureRecord("five", 0.9, ts)


def test_safe_repository_passes_through():
    fake = FakeRepository()
    repo = SafeRepository(fake)
    assert repo.save_command(CommandRecord("play_pause", "five", 1.0)) is True
    assert repo.save_gestures([g(1.0)]) is True
    assert fake.commands == [CommandRecord("play_pause", "five", 1.0)]
    assert fake.gesture_batches == [[g(1.0)]]


def test_safe_repository_swallows_errors(caplog):
    repo = SafeRepository(FakeRepository(fail=True))
    assert repo.save_command(CommandRecord("play_pause", "five", 1.0)) is False
    assert repo.save_gestures([g(1.0)]) is False
    assert "저장 실패" in caplog.text


def test_batcher_flushes_after_interval():
    b = GestureBatcher(interval_s=5.0)
    assert b.add(g(0.0)) is None
    assert b.add(g(4.9)) is None
    assert b.add(g(5.0)) == [g(0.0), g(4.9), g(5.0)]
    assert b.add(g(6.0)) is None  # 새 묶음 시작


def test_batcher_flushes_when_full():
    b = GestureBatcher(interval_s=100.0, max_size=3)
    assert b.add(g(0.0)) is None
    assert b.add(g(0.1)) is None
    assert b.add(g(0.2)) == [g(0.0), g(0.1), g(0.2)]


def test_drain_returns_leftovers():
    b = GestureBatcher()
    b.add(g(0.0))
    assert b.drain() == [g(0.0)]
    assert b.drain() == []
