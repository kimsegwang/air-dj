"""대시보드: http://localhost:<port>/  (노트북 안에서만 열린다)

    /            static/index.html
    /api/state   MQTT로 받은 제스처·명령 + mpv 곡 정보
    /api/board   보드 /result(손 박스) 중계. 보드 응답에 CORS 헤더가 없어 브라우저가 직접 못 읽는다.
카메라 영상은 브라우저가 보드 :81/stream을 <img>로 직접 받는다 (img는 CORS 제한 없음).
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

from air_dj_agent.mpv import Mpv
from air_dj_agent.state import MPV_PROPS, DashboardState, now_playing

log = logging.getLogger(__name__)

INDEX_HTML = Path(__file__).with_name("static") / "index.html"


def make_handler(state: DashboardState, mpv: Mpv, board_url: str):
    board = requests.Session()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", INDEX_HTML.read_bytes())
            elif path == "/api/state":
                body = state.snapshot()
                body["player"] = now_playing(mpv.get_properties(MPV_PROPS))
                body["board_url"] = board_url
                self._json(body)
            elif path == "/api/board":
                self._json(self._board_result())
            else:
                self._send(404, "text/plain", b"not found")

        def _board_result(self) -> dict:
            if not board_url:
                return {}
            try:
                return board.get(board_url + "/result", timeout=0.5).json()
            except (requests.RequestException, ValueError):
                return {}

        def _json(self, body: dict):
            self._send(200, "application/json", json.dumps(body, ensure_ascii=False).encode())

        def _send(self, code: int, ctype: str, data: bytes):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass  # 폴링 요청마다 로그가 찍히지 않게

    return Handler


def start_dashboard(state: DashboardState, mpv: Mpv, board_url: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state, mpv, board_url.rstrip("/")))
    threading.Thread(target=server.serve_forever, name="dashboard", daemon=True).start()
    log.info("대시보드: http://localhost:%d/", port)
    return server
