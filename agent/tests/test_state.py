from air_dj_agent.state import DashboardState, now_playing


def test_now_playing_prefers_metadata_case_insensitive():
    props = {
        "metadata": {"TITLE": "곡", "Artist": "가수", "album": "앨범"},
        "media-title": "fallback", "filename": "01 - x.flac",
        "time-pos": 12.5, "duration": 200.0, "pause": False, "volume": 80.0,
        "playlist-pos": 0, "playlist-count": 3,
        "playlist": [{"filename": r"C:\m\a.mp3"}, {"filename": r"C:\m\sub\b.flac"}, {"filename": r"C:\m\c.mp3"}],
    }
    p = now_playing(props)
    assert (p["title"], p["artist"], p["album"]) == ("곡", "가수", "앨범")
    assert (p["index"], p["count"], p["paused"]) == (1, 3, False)
    assert p["upcoming"] == ["b", "c"]


def test_now_playing_upcoming_wraps_around():
    playlist = [{"filename": f"{n}.mp3"} for n in "abc"]
    assert now_playing({"playlist-pos": 2, "playlist": playlist, "filename": "c.mp3"})["upcoming"] == ["a", "b"]


def test_now_playing_without_metadata_uses_file_stem():
    p = now_playing({"metadata": None, "media-title": None, "filename": "song name.mp3"})
    assert p["title"] == "song name" and p["artist"] is None


def test_now_playing_idle_and_unreachable():
    idle = now_playing({"filename": None, "playlist-pos": -1, "playlist-count": 0, "playlist": []})
    assert idle["available"] and not idle["loaded"] and idle["index"] is None and idle["upcoming"] == []
    assert now_playing({})["available"] is False


def test_state_snapshot():
    st = DashboardState(max_commands=2)
    st.on_gesture(b'{"label":"five","score":0.97,"det":0.8}', now=100.0)
    st.on_gesture(b"garbage", now=101.0)  # 무시
    for i, c in enumerate(("play", "next", "pause")):
        st.on_command(c, "x", True, now=100.0 + i)
    snap = st.snapshot(now=103.0)
    assert snap["gesture"]["label"] == "five" and snap["gesture_age"] == 3.0
    assert [c["command"] for c in snap["commands"]] == ["pause", "next"]
    assert snap["commands"][0]["ago"] == 1.0
