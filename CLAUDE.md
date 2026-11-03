# air-dj — 손 제스처 음악 플레이어

XIAO ESP32S3 Sense가 카메라로 손 제스처를 **온디바이스(ESP-DL)** 로 인식해 MQTT로 보내고,
라즈베리파이 5가 받아서 디바운스·명령 판단·Supabase 저장을 한 뒤 명령을 MQTT로 발행한다.
**음악은 윈도우 노트북에서 재생한다**(파이에는 스피커가 없음). 노트북의 플레이어 에이전트가 명령을 받아 mpv를 제어한다.

```
[XIAO ESP32S3 Sense] --air-dj/gesture--> [Pi5: mosquitto + receiver] --air-dj/commands--> [노트북: agent -> mpv -> 스피커]
   카메라 + ESP-DL                                   \--> Supabase (Postgres)
```

## 레포 구조
- `firmware/` — ESP-IDF 프로젝트 (esp32-camera + espressif/hand_detect + espressif/hand_gesture_recognition)
- `pi/` — 수신 서비스(Python, 파이에서 Docker로 실행), Dockerfile, requirements.txt, tests/
- `agent/` — 노트북 플레이어 에이전트(Python, conda `air-dj`에서 실행): `air-dj/commands` 구독 → mpv(named pipe)
- `supabase/schema.sql` — 테이블 생성 SQL (대시보드 SQL 에디터에서 수동 실행)
- `mosquitto/mosquitto.conf` — LAN 전용 브로커 설정 (파이 compose / 노트북 개발용 공용)
- `tools/serial_read.py` — 시리얼 로그를 N초 읽고 종료
- `docker-compose.yml` — mosquitto + receiver (파이에서 실행)
- `environment.yml` — conda 환경 (pip로 `pi/requirements.txt` 참조, receiver 개발과 agent 실행 공용)
- `.github/workflows/ci.yml` — 펌웨어 빌드(`espressif/esp-idf-ci-action@v1`, `esp_idf_version: v5.5.6`, `target: esp32s3`, `path: firmware`) / pytest / docker 이미지 빌드

## 절대 규칙
1. **conda 환경이 활성화된 상태에서 `idf.py` 실행 금지.** ESP-IDF는 EIM 환경에서만 실행한다.
   conda의 python/cmake/ninja가 PATH에 섞이면 빌드가 깨진다. 실행 전 `$env:CONDA_DEFAULT_ENV`가 비어 있는지 확인.
2. **`idf.py monitor` 사용 금지** (대화형). 로그는 `tools/serial_read.py`로 확인한다.
3. **비밀값 커밋 금지**: Wi-Fi SSID/비밀번호, 브로커 주소, Supabase URL/키/연결 문자열.
   - 펌웨어: Kconfig(menuconfig)로 설정 → `sdkconfig`는 gitignore, 커밋용 기본값은 `sdkconfig.defaults`(비밀값 없이)
   - 파이: `.env`(gitignore), 변수 이름만 `.env.example`에
   - 노트북 에이전트: `agent/.env`(gitignore), 변수 이름만 `agent/.env.example`에
   - Supabase secret 키(`sb_secret_...`)는 로그에도 남기지 않는다(요청 헤더 로깅 금지).
4. **ESP32와 노트북 에이전트는 Supabase에 직접 연결하지 않는다.** 저장은 파이 receiver만 한다.
5. **추론은 ESP32-S3에서.** 모델 학습 없음, 사전 학습 모델만 사용. ESP-WHO 프레임워크 전체는 쓰지 않는다.
6. **API/설정값은 추측하지 않는다.** `firmware/managed_components/` 안의 소스·예제, 공식 문서를 먼저 읽는다.
7. 단계별로 진행하고, 각 단계가 끝나면 (무엇을 했는지 / 어떻게 확인했는지 / 다음 할 일)을 보고하고 확인을 받는다.
   같은 방법으로 30분 넘게 막히면 반복하지 말고 원인 후보와 함께 보고한다.

## 하드웨어 메모
- 카메라는 **OV3660** (OV2640 아님). 상하 반전 시 `vflip` 설정 확인.
- XIAO Sense 카메라 핀:
  D0=15 D1=17 D2=18 D3=16 D4=14 D5=12 D6=11 D7=48,
  XCLK=10 PCLK=13 VSYNC=38 HREF=47 SDA=40 SCL=39 PWDN=-1 RESET=-1
- PSRAM 8MB(Octal), Flash 8MB. 초기화 직후 몇 프레임은 버린다.

## 제스처 인식 실측 (2026-11-03, 실내, QVGA)
- 프레임당 약 185ms(약 5.4fps): JPEG 디코딩 13 + 손 검출 171 + 분류 수 ms. 모델 PSRAM 약 0.75MB.
- ok/five/one/two/like는 분류 0.95~1.00, 검출(det) 0.6~0.9로 안정적.
- **dislike(👎)는 손 검출이 약하다**(det 0.27~0.5). dislike와 no_gesture가 번갈아 나와 명령까지 수 초 걸릴 수 있다. 사용자 판단으로 매핑은 유지.
- 들고 있는 중 1~2프레임 no_gesture/점수 하락이 섞인다 → 디바운스 `release_frames=5`(약 1초)로 재발화 방지.
- 같은 날 오후 실사용(파이 배포 후): 손이 보인 프레임의 71%가 no_gesture(점수 중앙값 0.999), one은 1~3프레임씩
  no_gesture와 번갈아 나왔다(no_gesture 연속 최대 23프레임). 원인(거리/손 각도/흔들림)은 미확인.
  → 디바운스를 "최근 5프레임 중 3프레임"으로 변경. 재발화는 no_hand 5프레임 또는 다른 손 모양 25프레임(약 5초) 후.
  같은 명령을 연달아 내려면 손을 화면 밖으로 1초 뺐다가 다시 한다.
- 파이 receiver(`pi/`)를 바꾸면 파이에서 `cd ~/air-dj && git pull && docker compose up -d --build receiver`.

## 펌웨어: 빌드 / 플래시 / 로그
**ESP-IDF 버전: v5.5.6 고정** (로컬 EIM과 CI `esp_idf_version` 모두 같은 값).
- v6.x를 쓰지 않는 이유: esp-dl README는 "release/v5.3 or above"만 명시하고, esp-dl 3.3.7은
  "do not support idf v6.0" 사유로 yank됐다. 최신 esp-dl 3.3.14의 v6 지원 근거는 없다.
- 그래서 ESP-IDF MCP 서버(`idf.py mcp-server`)는 쓰지 않는다. v6.0부터 있는 기능이기 때문이다. `idf.py`는 CLI로 실행한다.
- 버전을 올릴 때는 이 줄, EIM 설치, `.github/workflows/ci.yml`의 `esp_idf_version`을 함께 바꾼다.

설치 위치 (EIM 0.20.1, `winget install Espressif.eim`):
- ESP-IDF: `C:\esp\v5.5.6\esp-idf`
- 도구/파이썬 venv/설치 목록: `C:\Espressif\tools` (`eim_idf.json`, `python\v5.5.6\venv`)
- 활성화 스크립트: `C:\Espressif\tools\Microsoft.v5.5.6.PowerShell_profile.ps1`
- EIM 바이너리: `C:\Program Files\eim\eim.exe` (PATH에 없음, GUI 앱이라 직접 호출하면 출력이 안 보인다)

ESP-IDF 환경에서 명령 실행: **활성화 스크립트를 dot-source** 한다 (conda가 활성화돼 있으면 먼저 `conda deactivate`, base까지).
```powershell
. 'C:\Espressif\tools\Microsoft.v5.5.6.PowerShell_profile.ps1'
cd firmware
idf.py set-target esp32s3      # 최초 1회
idf.py menuconfig              # Wi-Fi/MQTT 설정 (sdkconfig에만 저장됨, 사람이 직접 실행)
idf.py build
idf.py -p COMx flash
```
Claude Code는 매 호출이 새 셸이므로 한 줄로 실행한다 (대화형 `menuconfig`/`monitor`는 실행하지 않는다):
```powershell
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ". 'C:\Espressif\tools\Microsoft.v5.5.6.PowerShell_profile.ps1' *> `$null; Set-Location firmware; idf.py build; exit `$LASTEXITCODE"
```
- 활성화 후 python/cmake/ninja/xtensa gcc가 모두 `C:\Espressif\tools` 쪽으로 잡히는 것을 확인했다
  (miniforge가 사용자 PATH에 상시 등록돼 있지만 활성화 스크립트가 앞에 붙인다).
- `eim run "idf.py build" v5.5.6`도 동작한다(작업 디렉터리 유지 확인). 단 출력이 보이지 않아
  `Start-Process -RedirectStandardOutput`이 필요하므로 기본 방법으로 쓰지 않는다.
- 참고: IDF venv의 기반 파이썬은 miniforge base(3.12.8)다. miniforge base를 업데이트/삭제하면
  venv가 깨질 수 있다. 그때는 EIM에서 v5.5.6을 재설치한다.

로그 확인 (conda 환경에서, `idf.py` 아님):
```powershell
conda activate air-dj
python tools/serial_read.py --port COMx --seconds 15
```

## MQTT 메시지
### `air-dj/gesture` (ESP32 → 파이 receiver)
- QoS 0, 매 프레임(약 5Hz) 발행. 손이 없어도 `no_hand`를 보낸다(디바운스가 "내림"을 알아야 함).
- 페이로드: `{"seq":123,"label":"five","score":0.970,"det":0.880,"ms":185}`
  - `label`: hand_gesture_recognition 라벨(one~five, like, ok, call, dislike, no_gesture, no_hand), 손 여러 개면 det 최고 하나
  - `score`: 제스처 분류 점수, `det`: 손 검출 점수(손 없으면 0), `ms`: 프레임 처리 시간, `seq`: 부팅 후 프레임 번호
- ESP32에는 시계가 없으므로 시각은 파이가 수신 시각으로 붙인다.
- 브로커 URI는 menuconfig > air-dj (sdkconfig에만). 노트북 개발용 브로커:
  `docker run -d --name air-dj-mqtt-dev -p 1883:1883 -v "${PWD}\mosquitto\mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" eclipse-mosquitto:2`

### `air-dj/commands` (파이 receiver → 노트북 agent)
- 디바운스를 통과한 명령만, 명령당 한 번 발행. QoS 1(유실 방지), retain 없음(재접속 시 옛 명령 재실행 방지).
- 페이로드: `{"command":"pause","label":"five","ts":1793679259.65}`
  - `command`: play | pause | next | prev | volume_up | volume_down, `ts`: 파이 수신 시각(epoch 초)

## Supabase (파이 receiver만 접속)
- REST(PostgREST) `https://<project_ref>.supabase.co/rest/v1/<table>`에 POST. 클라이언트 라이브러리 없이 HTTP로 직접.
- 키는 **secret 키**(`sb_secret_...`, RLS 우회). **`apikey` 헤더로만** 보낸다(새 키는 JWT가 아니므로 `Authorization: Bearer` 금지).
- 테이블은 RLS를 켜고 정책은 두지 않는다(publishable 키로는 접근 불가). secret 키가 쓰는 `service_role`에는 grant가 필요하다.
- 출처: supabase.com/docs/guides/api/api-keys, /guides/api/securing-your-api (2026-11-03 확인)

## 노트북 플레이어 에이전트 (`agent/`)
- conda `air-dj`에서 실행. `air-dj/commands`를 구독해 mpv를 제어한다.
- mpv는 에이전트가 `--input-ipc-server=\\.\pipe\<이름>`으로 띄운다(윈도우 IPC는 named pipe). 음악 폴더는 설정으로 지정.
- 브로커 주소(파이 IP), 음악 폴더 경로 등은 `agent/.env`(gitignore).
- mpv: `winget install shinchiro.mpv` → `C:\Program Files\MPV Player\mpv.exe`(PATH에 없음, `MPV_PATH`로 지정). 음악 폴더 `C:\Users\jjjkk\Desktop\air-dj-music`.
- mpv는 정지 상태로 시작한다(ok 제스처로 재생). 폴더 안 오디오 파일만 하위 폴더까지 재생목록에 넣고 반복한다.
- 실행: `conda activate air-dj; cd agent; python -m air_dj_agent` (종료는 Ctrl+C → mpv도 같이 종료)
- 대시보드: agent가 `http://localhost:8080/`을 띄우고 브라우저를 연다(127.0.0.1 전용, 표준 라이브러리 http.server).
  카메라는 브라우저가 보드 `:81/stream`을 직접 받고, 손 박스는 보드 `/result`에 CORS 헤더가 없어 agent `/api/board`가 중계한다.
  보드 스트림 서버는 한 번에 한 접속만 받는다(보드 미리보기 페이지와 동시에 열면 번갈아 끊긴다).
  agent는 화면 표시용으로 `air-dj/gesture`(QoS 0)도 구독한다.
- 테스트: `cd agent; pytest`. 실기 확인(2026-11-03): 6개 명령 모두 mpv 속성(pause/volume/playlist-pos)에 반영됨.
- 수동 테스트로 가짜 제스처를 보낼 때는 receiver `MQTT_TOPIC`을 다른 토픽으로 바꾼다. 보드가 켜져 있으면 실제 `no_hand`가 섞여 연속 프레임이 끊긴다.

## 파이 서비스: 개발 / 테스트 / 실행
노트북 (conda):
```powershell
conda env create -f environment.yml   # 최초 1회 (갱신: conda env update -f environment.yml --prune)
conda activate air-dj
pytest pi/tests
cd agent; pytest   # agent는 pytest.ini가 따로 있어 디렉터리에서 실행
```
- 패키지는 `pi/requirements.txt` 한 곳에서만 관리한다. `environment.yml`에 패키지를 직접 추가하지 않는다.
- 디바운스, 제스처→명령 매핑은 순수 함수. DB 접근은 저장소 인터페이스 뒤에 두고, 테스트/CI는 가짜 저장소를 쓴다.
- 저장 실패로 서비스가 죽으면 안 된다(로그만 남김). 명령은 즉시 저장, 제스처 원본은 몇 초 단위 일괄 저장.

라즈베리파이 5 (arm64): docker compose로 **mosquitto + receiver만** 실행한다(mpv/오디오는 파이에 없음).
```bash
cp .env.example .env   # 값 채우기
docker compose up -d --build
docker compose logs -f receiver
```
