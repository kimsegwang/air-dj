"""명령 → air-dj/commands (노트북 agent가 구독해 mpv를 제어한다).

페이로드 (CLAUDE.md "MQTT 메시지"):
    {"command":"pause","label":"five","ts":1793679259.65}
QoS 1(유실 방지), retain 없음(재접속 시 옛 명령 재실행 방지).
"""

import json
import logging
from typing import Protocol

from receiver.storage import CommandRecord

log = logging.getLogger(__name__)

COMMANDS_QOS = 1


def command_payload(record: CommandRecord) -> bytes:
    return json.dumps({"command": record.command, "label": record.label, "ts": round(record.ts, 2)}).encode()


class CommandSink(Protocol):
    def send(self, record: CommandRecord) -> bool: ...


class MqttCommandPublisher:
    """paho 클라이언트로 발행한다. 실패해도 예외를 던지지 않는다 (서비스가 죽으면 안 됨).

    브로커와 끊겨 있으면 버린다. paho가 큐에 쌓았다가 재접속 때 몰아서 보내면 옛 명령이 실행되기 때문.
    """

    def __init__(self, client, topic: str):
        self._client = client
        self._topic = topic

    def send(self, record: CommandRecord) -> bool:
        if not self._client.is_connected():
            log.warning("브로커 연결 끊김, 명령 버림: %s", record.command)
            return False
        info = self._client.publish(self._topic, command_payload(record), qos=COMMANDS_QOS, retain=False)
        if info.rc != 0:
            log.warning("명령 발행 실패 (rc=%s): %s", info.rc, record.command)
            return False
        return True
