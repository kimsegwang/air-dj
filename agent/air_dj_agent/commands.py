"""air-dj/commands 페이로드 → mpv 명령 (순수 함수).

페이로드 (CLAUDE.md "MQTT 메시지"):
    {"command":"pause","label":"five","ts":1793679259.65}
mpv 명령은 DOCS/man/input.rst 기준. playlist-next/prev 기본(weak)은 끝/처음에서 아무것도 안 함,
add는 범위를 넘으면 clamp.
"""

import json

VOLUME_STEP = 10

MPV_COMMANDS: dict[str, list] = {
    "play": ["set_property", "pause", False],
    "pause": ["set_property", "pause", True],
    "next": ["playlist-next"],
    "prev": ["playlist-prev"],
    "volume_up": ["add", "volume", VOLUME_STEP],
    "volume_down": ["add", "volume", -VOLUME_STEP],
}


def parse_command(payload: bytes) -> str | None:
    """모르는 명령이나 형식이 틀리면 None (agent는 무시하고 계속 돈다)."""
    try:
        command = json.loads(payload)["command"]
    except (ValueError, KeyError, TypeError):
        return None
    return command if isinstance(command, str) and command in MPV_COMMANDS else None
