"""python -m air_dj_agent   (agent/ 에서, conda air-dj)

설정은 agent/.env (agent/.env.example 참고):
    MQTT_HOST, MQTT_PORT, COMMANDS_TOPIC, GESTURE_TOPIC
    MUSIC_DIR(처음 기본값, 대시보드에서 고르면 agent/settings.json이 우선), MPV_PATH, MPV_PIPE
    BOARD_URL, DASHBOARD_PORT, OPEN_BROWSER
"""

import logging
import os
import signal
import webbrowser
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from air_dj_agent.commands import MPV_COMMANDS, parse_command
from air_dj_agent.dashboard import start_dashboard
from air_dj_agent.library import SETTINGS_FILE, MusicLibrary, initial_music_dir
from air_dj_agent.mpv import Mpv
from air_dj_agent.state import DashboardState

log = logging.getLogger("agent")

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if ENV_FILE.exists():
        load_env(ENV_FILE)

    host = os.environ.get("MQTT_HOST", "localhost")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    commands_topic = os.environ.get("COMMANDS_TOPIC", "air-dj/commands")
    gesture_topic = os.environ.get("GESTURE_TOPIC", "air-dj/gesture")
    music_dir = initial_music_dir(SETTINGS_FILE, os.environ.get("MUSIC_DIR"))
    if music_dir is None:
        log.warning("음악 폴더가 없음 → 대시보드에서 [폴더 선택]으로 고른다")

    mpv = Mpv(
        os.environ.get("MPV_PATH", "mpv"),
        os.environ.get("MPV_PIPE", r"\\.\pipe\air-dj-mpv"),
        music_dir,
    )
    mpv.start()

    state = DashboardState()
    dashboard_port = int(os.environ.get("DASHBOARD_PORT", "8080"))
    dashboard = start_dashboard(state, mpv, MusicLibrary(mpv), os.environ.get("BOARD_URL", ""), dashboard_port)
    if os.environ.get("OPEN_BROWSER", "1") == "1":
        webbrowser.open(f"http://localhost:{dashboard_port}/")

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("MQTT connected to %s:%d (%s), subscribing %s, %s", host, port, reason_code, commands_topic, gesture_topic)
        state.mqtt_connected = True
        # 재접속 때마다 다시 구독. 제스처는 화면 표시용이라 QoS 0
        client.subscribe([(commands_topic, 1), (gesture_topic, 0)])

    def on_disconnect(client, userdata, flags, reason_code, properties):
        log.warning("MQTT disconnected (%s), reconnecting", reason_code)
        state.mqtt_connected = False

    def on_message(client, userdata, message):
        try:
            if message.topic == gesture_topic:
                state.on_gesture(message.payload)
                return
            parsed = parse_command(message.payload)
            if parsed is None:
                log.warning("모르는 명령 무시: %r", message.payload[:200])
                return
            command, label = parsed
            ok = mpv.command(MPV_COMMANDS[command])
            state.on_command(command, label, ok)
            log.info("%s -> %s", command, "ok" if ok else "실패")
        except Exception:
            log.exception("메시지 처리 실패")  # agent는 계속 돈다

    # clean session(기본값): 꺼져 있던 동안의 명령은 받지 않는다 (옛 명령 재실행 방지)
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="air-dj-agent")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def stop(signum, frame):
        client.disconnect()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    log.info("broker=%s:%d, music=%s", host, port, music_dir or "(없음)")
    client.connect_async(host, port)
    try:
        client.loop_forever(retry_first_connection=True)
    finally:
        dashboard.shutdown()
        mpv.stop()
        log.info("stopped")


if __name__ == "__main__":
    main()
