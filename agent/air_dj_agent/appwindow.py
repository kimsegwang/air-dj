"""대시보드를 Edge 앱 창(주소창 없는 별도 창)으로 띄우고, 창이 닫히면 알린다.

전용 프로필(--user-data-dir)을 쓰면 평소 쓰는 Edge와 별개 프로세스로 뜬다. 그 프로세스는 창이 열려 있는 동안
살아 있고 창을 닫으면 끝난다(2026-11-03, WM_CLOSE로 확인). 이미 같은 프로필 창이 떠 있으면 새 프로세스가
그쪽에 넘기고 바로 끝나므로, 너무 빨리 끝나면 "닫힘"으로 보지 않는다.
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

EDGE_CANDIDATES = [
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
]
PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "air-dj" / "edge-app-profile"
HANDOFF_S = 3.0  # 이보다 빨리 끝나면 기존 창에 넘긴 것으로 본다


def find_edge() -> Path | None:
    return next((p for p in EDGE_CANDIDATES if p.is_file()), None)


def app_args(edge: Path, url: str, profile: Path) -> list[str]:
    return [str(edge), f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--window-size=1400,900"]


def open_app_window(url: str, on_closed: Callable[[], None]) -> bool:
    """앱 창을 띄우고, 사용자가 닫으면 on_closed를 부른다. Edge가 없으면 False."""
    edge = find_edge()
    if edge is None:
        return False
    started = time.monotonic()
    proc = subprocess.Popen(app_args(edge, url, PROFILE_DIR))

    def watch():
        proc.wait()
        if time.monotonic() - started < HANDOFF_S:
            log.warning("대시보드 창이 이미 떠 있는 창에 넘어감 → 창을 닫아도 agent는 계속 돈다 (끄려면 Ctrl+C)")
            return
        log.info("대시보드 창이 닫힘 → 종료")
        on_closed()

    threading.Thread(target=watch, name="app-window", daemon=True).start()
    return True
