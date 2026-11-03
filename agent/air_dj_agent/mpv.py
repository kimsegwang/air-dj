r"""mpv를 띄우고 JSON IPC로 제어한다.

mpv JSON IPC (DOCS/man/ipc.rst): 한 줄에 JSON 하나, "\n"으로 끝난다.
    {"command": ["set_property", "pause", true], "request_id": 1}
응답 {"error": "success", ...}과 이벤트 {"event": ...}가 같은 연결로 섞여 온다.
윈도우에서 --input-ipc-server는 named pipe(\\.\pipe\<이름>)이고, 파일처럼 열어 읽고 쓴다.
"""

import itertools
import json
import logging
import subprocess
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)


def mpv_args(mpv_path: str, pipe: str, music_dir: str) -> list[str]:
    return [
        mpv_path,
        f"--input-ipc-server={pipe}",
        "--idle=yes",                      # 재생목록이 끝나거나 비어도 종료하지 않는다
        "--pause",                         # 시작은 정지 상태, ok 제스처로 재생
        "--loop-playlist=inf",
        "--vid=no",
        "--audio-display=no",              # 앨범 아트 창을 띄우지 않는다
        "--force-window=no",
        "--terminal=no",
        "--directory-mode=recursive",
        "--directory-filter-types=audio",
        music_dir,
    ]


def read_replies(read: Callable[[int], bytes], request_ids: set[int]) -> dict[int, dict]:
    """이벤트 줄은 건너뛰고 request_ids의 응답을 모두 모은다."""
    replies: dict[int, dict] = {}
    buf = b""
    while len(replies) < len(request_ids):
        chunk = read(4096)
        if not chunk:
            raise OSError("mpv closed the connection")
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "event" not in msg and msg.get("request_id") in request_ids:
                replies[msg["request_id"]] = msg
    return replies


class Mpv:
    """mpv 프로세스 하나를 관리한다. 꺼져 있으면 다음 요청 때 다시 띄운다.

    요청마다 파이프를 새로 연다 (MQTT 스레드와 대시보드 스레드가 동시에 써도 각자 연결).
    실패해도 예외를 던지지 않는다 (agent가 죽으면 안 됨).
    """

    def __init__(self, mpv_path: str, pipe: str, music_dir: str, start_timeout_s: float = 5.0):
        self._args = mpv_args(mpv_path, pipe, music_dir)
        self._pipe = pipe
        self._start_timeout = start_timeout_s
        self._proc: subprocess.Popen | None = None
        self._start_lock = threading.Lock()
        self._ids = itertools.count(1)

    def start(self) -> None:
        with self._start_lock:
            if self._proc is not None and self._proc.poll() is None:
                return
            log.info("mpv 시작: %s", " ".join(self._args))
            self._proc = subprocess.Popen(self._args)

    def stop(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            return
        self.command(["quit"])
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()

    def command(self, cmd: list) -> bool:
        replies = self._request([cmd])
        if replies is None:
            return False
        error = replies[0].get("error")
        if error != "success":
            log.warning("mpv %s 오류: %s", cmd[0], error)
            return False
        return True

    def get_properties(self, names: list[str]) -> dict:
        """연결 한 번으로 여러 속성을 읽는다. 없는 속성(재생 중인 파일이 없을 때 등)은 None."""
        replies = self._request([["get_property", name] for name in names])
        if replies is None:
            return {}
        return {name: (r.get("data") if r.get("error") == "success" else None) for name, r in zip(names, replies)}

    def _request(self, cmds: list[list]) -> list[dict] | None:
        self.start()
        ids = [next(self._ids) for _ in cmds]
        payload = b"".join(json.dumps({"command": c, "request_id": i}).encode() + b"\n" for c, i in zip(cmds, ids))
        try:
            with self._open_pipe() as f:
                f.write(payload)
                replies = read_replies(f.read, set(ids))
        except OSError as e:
            log.warning("mpv %s 실패: %s", cmds[0][0], e)
            return None
        return [replies[i] for i in ids]

    def _open_pipe(self):
        """mpv를 막 띄웠으면 파이프가 생길 때까지 기다린다."""
        deadline = time.monotonic() + self._start_timeout
        while True:
            try:
                return open(self._pipe, "r+b", buffering=0)
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
