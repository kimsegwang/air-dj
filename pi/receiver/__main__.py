"""python -m receiver

환경 변수 (.env.example 참고):
    MQTT_HOST, MQTT_PORT, MQTT_TOPIC
    PLAYER=log|mpv, MPV_SOCKET
    SUPABASE_URL, SUPABASE_SECRET_KEY (없으면 로그만 남긴다)
"""

import logging
import os
import signal
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from receiver.player import LogPlayer, MpvPlayer
from receiver.service import Receiver
from receiver.storage import BackgroundRepository, SafeRepository
from receiver.supabase import SupabaseRepository

log = logging.getLogger("receiver")


class LogRepository:
    """Supabase 연결 전까지 쓰는 저장소: 로그만 남긴다."""

    def save_command(self, record):
        log.info("save command: %s", record)

    def save_gestures(self, records):
        log.info("save %d gestures", len(records))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    host = os.environ.get("MQTT_HOST", "localhost")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    topic = os.environ.get("MQTT_TOPIC", "air-dj/gesture")
    player_kind = os.environ.get("PLAYER", "log")

    player = MpvPlayer(os.environ.get("MPV_SOCKET", "/tmp/mpvsocket")) if player_kind == "mpv" else LogPlayer()

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if supabase_url and supabase_key:
        inner = SupabaseRepository(supabase_url, supabase_key)
        log.info("storage: supabase (%s)", supabase_url)  # 키는 로그에 남기지 않는다
    else:
        inner = LogRepository()
        log.warning("storage: SUPABASE_URL/SUPABASE_SECRET_KEY 없음 → 로그만 남긴다")
    repo = BackgroundRepository(SafeRepository(inner))
    receiver = Receiver(player, repo)

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("MQTT connected to %s:%d (%s), subscribing %s", host, port, reason_code, topic)
        client.subscribe(topic, qos=0)  # 재접속 때마다 다시 구독

    def on_disconnect(client, userdata, flags, reason_code, properties):
        log.warning("MQTT disconnected (%s), reconnecting", reason_code)

    def on_message(client, userdata, message):
        try:
            receiver.handle(message.payload, time.time())
        except Exception:
            log.exception("메시지 처리 실패")  # 서비스는 계속 돈다

    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="air-dj-receiver")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def stop(signum, frame):
        client.disconnect()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log.info("player=%s, broker=%s:%d", player_kind, host, port)
    client.connect_async(host, port)
    try:
        client.loop_forever(retry_first_connection=True)
    finally:
        receiver.flush()
        repo.close()
        log.info("stopped")


if __name__ == "__main__":
    main()
