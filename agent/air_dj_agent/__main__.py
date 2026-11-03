"""python -m air_dj_agent   (agent/ 에서, conda air-dj)

설정은 agent/.env (agent/.env.example 참고):
    MQTT_HOST, MQTT_PORT, COMMANDS_TOPIC
    MUSIC_DIR, MPV_PATH, MPV_PIPE
"""

import logging
import os
import signal
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from air_dj_agent.commands import MPV_COMMANDS, parse_command
from air_dj_agent.mpv import Mpv

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
    topic = os.environ.get("COMMANDS_TOPIC", "air-dj/commands")
    music_dir = os.environ.get("MUSIC_DIR", "")
    if not music_dir or not Path(music_dir).is_dir():
        raise SystemExit(f"MUSIC_DIR가 없거나 폴더가 아님: {music_dir!r} (agent/.env 확인)")

    mpv = Mpv(
        os.environ.get("MPV_PATH", "mpv"),
        os.environ.get("MPV_PIPE", r"\\.\pipe\air-dj-mpv"),
        music_dir,
    )
    mpv.start()

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("MQTT connected to %s:%d (%s), subscribing %s", host, port, reason_code, topic)
        client.subscribe(topic, qos=1)  # 재접속 때마다 다시 구독

    def on_disconnect(client, userdata, flags, reason_code, properties):
        log.warning("MQTT disconnected (%s), reconnecting", reason_code)

    def on_message(client, userdata, message):
        try:
            command = parse_command(message.payload)
            if command is None:
                log.warning("모르는 명령 무시: %r", message.payload[:200])
                return
            ok = mpv.command(MPV_COMMANDS[command])
            log.info("%s -> %s", command, "ok" if ok else "실패")
        except Exception:
            log.exception("명령 처리 실패")  # agent는 계속 돈다

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

    log.info("broker=%s:%d, music=%s", host, port, music_dir)
    client.connect_async(host, port)
    try:
        client.loop_forever(retry_first_connection=True)
    finally:
        mpv.stop()
        log.info("stopped")


if __name__ == "__main__":
    main()
