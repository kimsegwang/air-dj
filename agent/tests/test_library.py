import json

from air_dj_agent.library import MusicLibrary, initial_music_dir, save_music_dir


class FakeMpv:
    def __init__(self, ok=True, music_dir=None):
        self.ok = ok
        self.music_dir = music_dir
        self.loaded = []

    def load_dir(self, music_dir):
        self.loaded.append(music_dir)
        if self.ok:
            self.music_dir = music_dir
        return self.ok


def test_initial_prefers_saved_then_env(tmp_path):
    saved, env = tmp_path / "saved", tmp_path / "env"
    saved.mkdir(); env.mkdir()
    settings = tmp_path / "settings.json"
    assert initial_music_dir(settings, str(env)) == str(env)  # 저장된 것 없음
    save_music_dir(settings, str(saved))
    assert initial_music_dir(settings, str(env)) == str(saved)


def test_initial_skips_missing_dirs_and_broken_file(tmp_path):
    settings = tmp_path / "settings.json"
    save_music_dir(settings, str(tmp_path / "gone"))
    assert initial_music_dir(settings, str(tmp_path / "also-gone")) is None
    settings.write_text("not json", encoding="utf-8")
    assert initial_music_dir(settings, None) is None


def test_choose_loads_and_saves(tmp_path):
    music = tmp_path / "music"; music.mkdir()
    settings = tmp_path / "settings.json"
    mpv = FakeMpv()
    r = MusicLibrary(mpv, settings, ask=lambda initial: str(music)).choose()
    assert r == {"ok": True, "music_dir": str(music)}
    assert mpv.loaded == [str(music)]
    assert json.loads(settings.read_text(encoding="utf-8"))["music_dir"] == str(music)


def test_choose_cancel_changes_nothing(tmp_path):
    mpv = FakeMpv(music_dir="x")
    r = MusicLibrary(mpv, tmp_path / "s.json", ask=lambda initial: None).choose()
    assert r["ok"] is False and mpv.loaded == [] and not (tmp_path / "s.json").exists()


def test_player_failure_is_not_saved(tmp_path):
    music = tmp_path / "music"; music.mkdir()
    r = MusicLibrary(FakeMpv(ok=False), tmp_path / "s.json", ask=lambda initial: str(music)).choose()
    assert r["ok"] is False and not (tmp_path / "s.json").exists()


def test_reload_uses_current_dir(tmp_path):
    music = tmp_path / "music"; music.mkdir()
    mpv = FakeMpv(music_dir=str(music))
    assert MusicLibrary(mpv, tmp_path / "s.json").reload()["ok"] is True
    assert mpv.loaded == [str(music)]
    assert MusicLibrary(FakeMpv(), tmp_path / "s.json").reload()["ok"] is False
