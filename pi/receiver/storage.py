"""저장소 인터페이스와 저장 정책.

실제 DB(Supabase) 구현은 Repository를 따르는 별도 클래스로 둔다. 테스트는 가짜 저장소를 쓴다.
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol, Sequence

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GestureRecord:
    label: str
    score: float
    ts: float


@dataclass(frozen=True)
class CommandRecord:
    command: str
    label: str
    ts: float


class Repository(Protocol):
    def save_command(self, record: CommandRecord) -> None: ...
    def save_gestures(self, records: Sequence[GestureRecord]) -> None: ...


class SafeRepository:
    """저장 실패를 삼키고 로그만 남긴다. 서비스가 저장 때문에 죽지 않게 한다."""

    def __init__(self, inner: Repository):
        self._inner = inner

    def save_command(self, record: CommandRecord) -> bool:
        try:
            self._inner.save_command(record)
            return True
        except Exception:
            log.exception("명령 저장 실패: %s", record)
            return False

    def save_gestures(self, records: Sequence[GestureRecord]) -> bool:
        try:
            self._inner.save_gestures(records)
            return True
        except Exception:
            log.exception("제스처 %d건 저장 실패", len(records))
            return False


@dataclass
class GestureBatcher:
    """제스처 원본을 모았다가 interval_s마다 한 번에 내보낸다."""

    interval_s: float = 5.0
    max_size: int = 500
    _buffer: list[GestureRecord] = field(default_factory=list)
    _started_at: float | None = None

    def add(self, record: GestureRecord) -> list[GestureRecord] | None:
        """기록을 추가하고, 내보낼 때가 되면 묶음을 돌려준다."""
        if self._started_at is None:
            self._started_at = record.ts
        self._buffer.append(record)
        if record.ts - self._started_at >= self.interval_s or len(self._buffer) >= self.max_size:
            return self.drain()
        return None

    def drain(self) -> list[GestureRecord]:
        """남은 기록을 모두 꺼낸다 (종료 시에도 호출)."""
        batch, self._buffer, self._started_at = self._buffer, [], None
        return batch
