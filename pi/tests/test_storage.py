from fakes import FakeRepository
from receiver.storage import BackgroundRepository, CommandRecord, GestureBatcher, GestureRecord, SafeRepository


def g(ts):
    return GestureRecord("five", 0.9, ts)


def test_safe_repository_passes_through():
    fake = FakeRepository()
    repo = SafeRepository(fake)
    assert repo.save_command(CommandRecord("pause", "five", 1.0)) is True
    assert repo.save_gestures([g(1.0)]) is True
    assert fake.commands == [CommandRecord("pause", "five", 1.0)]
    assert fake.gesture_batches == [[g(1.0)]]


def test_safe_repository_swallows_errors(caplog):
    repo = SafeRepository(FakeRepository(fail=True))
    assert repo.save_command(CommandRecord("pause", "five", 1.0)) is False
    assert repo.save_gestures([g(1.0)]) is False
    assert "저장 실패" in caplog.text


def test_background_repository_saves_everything_before_close():
    fake = FakeRepository()
    repo = BackgroundRepository(SafeRepository(fake))
    repo.save_command(CommandRecord("pause", "five", 1.0))
    repo.save_gestures([g(1.0), g(2.0)])
    repo.close()
    assert fake.commands == [CommandRecord("pause", "five", 1.0)]
    assert fake.gesture_batches == [[g(1.0), g(2.0)]]


def test_background_repository_survives_failures():
    repo = BackgroundRepository(SafeRepository(FakeRepository(fail=True)))
    repo.save_command(CommandRecord("pause", "five", 1.0))
    repo.close()  # 예외 없이 끝나야 한다


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
