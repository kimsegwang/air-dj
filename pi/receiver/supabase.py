"""Supabase REST(PostgREST) 저장소.

- POST https://<project_ref>.supabase.co/rest/v1/<table>, JSON 배열이면 일괄 insert
- secret 키(sb_secret_...)는 apikey 헤더로만 보낸다 (JWT가 아니므로 Authorization: Bearer 금지)
- 키를 로그/예외 메시지에 넣지 않는다
"""

from datetime import datetime, timezone
from typing import Sequence

import requests

from receiver.storage import CommandRecord, GestureRecord

COMMANDS_TABLE = "gesture_commands"
FRAMES_TABLE = "gesture_frames"


def to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def command_row(record: CommandRecord) -> dict:
    return {"received_at": to_iso(record.ts), "command": record.command, "label": record.label}


def gesture_row(record: GestureRecord) -> dict:
    return {"received_at": to_iso(record.ts), "label": record.label, "score": record.score}


class SupabaseRepository:
    def __init__(self, url: str, secret_key: str, session: requests.Session | None = None, timeout_s: float = 5.0):
        self._base = url.rstrip("/") + "/rest/v1/"
        self._session = session or requests.Session()
        self._headers = {
            "apikey": secret_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        self._timeout = timeout_s

    def save_command(self, record: CommandRecord) -> None:
        self._insert(COMMANDS_TABLE, [command_row(record)])

    def save_gestures(self, records: Sequence[GestureRecord]) -> None:
        self._insert(FRAMES_TABLE, [gesture_row(r) for r in records])

    def _insert(self, table: str, rows: list[dict]) -> None:
        resp = self._session.post(self._base + table, json=rows, headers=self._headers, timeout=self._timeout)
        if resp.status_code >= 300:
            raise RuntimeError(f"{table} insert failed: HTTP {resp.status_code} {resp.text[:300]}")
