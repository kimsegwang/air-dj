"""Supabase 연결/권한 확인: .env를 읽어 gesture_commands에 테스트 행 1개를 넣고 다시 읽는다.

    python tools/supabase_check.py            (레포 루트의 .env 사용)

키는 출력하지 않는다. 테스트 행은 label='selftest'로 들어간다.
"""

import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi"))
from receiver.storage import CommandRecord  # noqa: E402
from receiver.supabase import COMMANDS_TABLE, SupabaseRepository  # noqa: E402


def load_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        print(f".env 없음: {env}")
        return 1
    load_env(env)
    url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        print("SUPABASE_URL 또는 SUPABASE_SECRET_KEY가 비어 있음")
        return 1
    print(f"url: {url}")
    print(f"key: {key[:10]}... ({len(key)} chars)")
    if not key.startswith("sb_secret_"):
        print("경고: secret 키(sb_secret_...)가 아닌 것 같음")

    ts = time.time()
    try:
        SupabaseRepository(url, key).save_command(CommandRecord("play", "selftest", ts))
        print("insert: OK")
    except Exception as e:
        print(f"insert: FAIL {e}")
        return 1

    resp = requests.get(
        url.rstrip("/") + f"/rest/v1/{COMMANDS_TABLE}",
        params={"select": "id,received_at,command,label", "label": "eq.selftest", "order": "id.desc", "limit": "3"},
        headers={"apikey": key},
        timeout=5,
    )
    print(f"select: HTTP {resp.status_code} {resp.text[:300]}")
    return 0 if resp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
