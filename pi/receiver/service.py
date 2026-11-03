"""메시지 하나를 받아 디바운스 → 플레이어 → 저장까지 처리한다. MQTT와 분리돼 있어 테스트에서 바로 부른다."""

import logging

from receiver.gestures import DEFAULT_MAPPING, Command, DebounceConfig, DebounceState, step
from receiver.message import parse_gesture
from receiver.player import Player
from receiver.storage import CommandRecord, GestureBatcher, GestureRecord, SafeRepository

log = logging.getLogger(__name__)

# 원본 저장에서 뺄 라벨 (손이 없을 때 5Hz로 계속 들어온다)
NOT_STORED = {"no_hand"}


class Receiver:
    def __init__(
        self,
        player: Player,
        repo: SafeRepository,
        config: DebounceConfig = DebounceConfig(),
        mapping: dict[str, Command] = DEFAULT_MAPPING,
        batcher: GestureBatcher | None = None,
    ):
        self._player = player
        self._repo = repo
        self._config = config
        self._mapping = mapping
        self._batcher = batcher or GestureBatcher()
        self._state = DebounceState()

    def handle(self, payload: bytes, received_at: float) -> Command | None:
        gesture = parse_gesture(payload, received_at)
        if gesture is None:
            log.warning("잘못된 메시지 무시: %r", payload[:200])
            return None

        if gesture.label not in NOT_STORED:
            batch = self._batcher.add(GestureRecord(gesture.label, gesture.score, gesture.ts))
            if batch:
                self._repo.save_gestures(batch)

        self._state, command = step(self._state, gesture, self._config, self._mapping)
        if command is None:
            return None

        log.info("%s (%s %.2f)", command.value, gesture.label, gesture.score)
        self._player.execute(command)
        self._repo.save_command(CommandRecord(command.value, gesture.label, gesture.ts))
        return command

    def flush(self) -> None:
        """종료 시 남은 제스처 원본을 저장한다."""
        batch = self._batcher.drain()
        if batch:
            self._repo.save_gestures(batch)
