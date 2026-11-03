"""음악 폴더: 대시보드에서 고르고, 다음 실행 때도 쓰도록 agent/settings.json(gitignore)에 저장한다.

우선순위: settings.json(마지막으로 고른 폴더) → agent/.env의 MUSIC_DIR → 없음(빈 재생목록, 대시보드에서 고른다)
"""

import json
import logging
import threading
from pathlib import Path

from air_dj_agent.mpv import Mpv

log = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "settings.json"


def initial_music_dir(settings_file: Path, env_dir: str | None) -> str | None:
    """존재하는 폴더만 돌려준다 (USB 드라이브를 뺐거나 폴더를 지웠을 수 있다)."""
    try:
        saved = json.loads(settings_file.read_text(encoding="utf-8")).get("music_dir")
    except (OSError, ValueError, AttributeError):
        saved = None
    for candidate in (saved, env_dir):
        if candidate and Path(candidate).is_dir():
            return candidate
    return None


def save_music_dir(settings_file: Path, music_dir: str) -> None:
    settings_file.write_text(json.dumps({"music_dir": music_dir}, ensure_ascii=False, indent=2), encoding="utf-8")


def ask_directory(initial: str | None) -> str | None:
    """윈도우 폴더 선택 창. 노트북 화면 맨 앞에 뜨고, 고를 때까지 기다린다. 취소하면 None."""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # 브라우저 뒤에 숨지 않게
    try:
        chosen = filedialog.askdirectory(parent=root, initialdir=initial or str(Path.home()),
                                         title="air-dj 음악 폴더 선택", mustexist=True)
    finally:
        root.destroy()
    return str(Path(chosen)) if chosen else None


class MusicLibrary:
    def __init__(self, mpv: Mpv, settings_file: Path = SETTINGS_FILE, ask=ask_directory):
        self._mpv = mpv
        self._settings = settings_file
        self._ask = ask
        self._dialog_lock = threading.Lock()

    @property
    def music_dir(self) -> str | None:
        return self._mpv.music_dir

    def choose(self) -> dict:
        """폴더 선택 창을 띄워 고른 폴더로 바꾼다. 창은 한 번에 하나만."""
        if not self._dialog_lock.acquire(blocking=False):
            return {"ok": False, "error": "폴더 선택 창이 이미 열려 있습니다"}
        try:
            chosen = self._ask(self.music_dir)
        finally:
            self._dialog_lock.release()
        if chosen is None:
            return {"ok": False, "error": "취소됨"}
        return self._load(chosen)

    def reload(self) -> dict:
        """같은 폴더를 다시 읽는다 (곡을 추가/삭제한 뒤). 재생목록 처음부터 시작한다."""
        if not self.music_dir:
            return {"ok": False, "error": "음악 폴더가 정해지지 않았습니다"}
        return self._load(self.music_dir)

    def _load(self, music_dir: str) -> dict:
        if not Path(music_dir).is_dir():
            return {"ok": False, "error": f"폴더가 없습니다: {music_dir}"}
        if not self._mpv.load_dir(music_dir):
            return {"ok": False, "error": "플레이어가 응답하지 않습니다"}
        try:
            save_music_dir(self._settings, music_dir)
        except OSError as e:
            log.warning("음악 폴더 저장 실패: %s", e)  # 이번 실행에는 적용됐으니 계속
        log.info("음악 폴더: %s", music_dir)
        return {"ok": True, "music_dir": music_dir}
