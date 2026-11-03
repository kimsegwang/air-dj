"""명령 → 플레이어.

mpv JSON IPC (DOCS/man/ipc.rst): 한 줄에 JSON 하나, "\n"으로 끝난다.
    {"command": ["set_property", "pause", true], "request_id": 1}
응답 {"error": "success", ...}과 이벤트 {"event": ...}가 같은 소켓으로 섞여 온다.
"""

import json
import logging
import socket
from typing import Protocol

from receiver.gestures import Command

log = logging.getLogger(__name__)

VOLUME_STEP = 10

# input.rst: playlist-next/prev 기본(weak)은 끝/처음에서 아무것도 안 함, add는 범위를 넘으면 clamp
MPV_COMMANDS: dict[Command, list] = {
    Command.PLAY: ["set_property", "pause", False],
    Command.PAUSE: ["set_property", "pause", True],
    Command.NEXT: ["playlist-next"],
    Command.PREV: ["playlist-prev"],
    Command.VOLUME_UP: ["add", "volume", VOLUME_STEP],
    Command.VOLUME_DOWN: ["add", "volume", -VOLUME_STEP],
}


class Player(Protocol):
    def execute(self, command: Command) -> bool: ...


class LogPlayer:
    """mpv 없이 개발할 때: 명령을 로그로만 남긴다."""

    def execute(self, command: Command) -> bool:
        log.info("player <- %s", command.value)
        return True


class MpvPlayer:
    """mpv --input-ipc-server=<socket_path> 로 띄운 mpv를 유닉스 소켓으로 제어한다.

    명령마다 새로 연결한다 (mpv가 재시작돼도 다음 명령부터 다시 동작).
    실패해도 예외를 던지지 않는다 (서비스가 죽으면 안 됨).
    """

    def __init__(self, socket_path: str, timeout_s: float = 1.0):
        self._path = socket_path
        self._timeout = timeout_s
        self._request_id = 0

    def execute(self, command: Command) -> bool:
        self._request_id += 1
        request = {"command": MPV_COMMANDS[command], "request_id": self._request_id}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self._timeout)
                sock.connect(self._path)
                sock.sendall(json.dumps(request).encode() + b"\n")
                reply = self._read_reply(sock, self._request_id)
        except OSError as e:
            log.warning("mpv %s 실패: %s", command.value, e)
            return False
        if reply.get("error") != "success":
            log.warning("mpv %s 오류: %s", command.value, reply.get("error"))
            return False
        return True

    @staticmethod
    def _read_reply(sock: socket.socket, request_id: int) -> dict:
        """이벤트 줄은 건너뛰고 request_id가 같은 응답을 찾는다."""
        buf = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                raise OSError("mpv closed the connection")
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if "event" not in msg and msg.get("request_id") == request_id:
                    return msg
