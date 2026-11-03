# air-dj

카메라 앞에서 손 제스처를 하면 노트북의 음악이 재생/정지/곡 넘김/볼륨 조절되는 프로젝트.

```
[XIAO ESP32S3 Sense] --air-dj/gesture--> [라즈베리파이 5: mosquitto + receiver] --air-dj/commands--> [노트북: agent → mpv → 스피커]
  카메라 + 손 제스처 인식(ESP-DL)                 디바운스 → 명령          \--> Supabase(기록)            + 대시보드(브라우저)
```

- **보드**(XIAO ESP32S3 Sense): 카메라로 손을 찾고 제스처를 분류해(사전 학습 모델, 온디바이스) 매 프레임 MQTT로 보낸다.
- **라즈베리파이 5**: 브로커(mosquitto)와 receiver를 Docker로 실행. 제스처가 잠깐 깜빡이는 것을 걸러(디바운스) 명령을 한 번만 내고, 기록을 Supabase에 저장한다.
- **노트북**: agent가 명령을 받아 mpv로 음악을 재생하고, 대시보드 화면을 띄운다.

## 제스처

| 제스처 | 명령 |
|---|---|
| 👌 ok | 재생 |
| ✋ 손바닥(five) | 정지 |
| ☝️ 손가락 하나(one) | 다음 곡 |
| ✌️ 손가락 둘(two) | 이전 곡 |
| 👍 like | 볼륨 + |
| 👎 dislike | 볼륨 − |

- 제스처를 약 0.6~1초 유지하면 명령이 나간다. 들고 있는 동안은 한 번만 실행된다.
- **같은 명령을 연달아 하려면 손을 화면 밖으로 1초 뺐다가 다시** 한다. 다른 제스처로 바꾸면 바로 반응한다.
- 배경이 깔끔하고, 손바닥이 카메라를 향하고, 50cm~1m 거리일 때 인식이 잘 된다.
- 👎 dislike는 손 검출이 약해 몇 초 걸릴 수 있다.

## 노트북에서 실행 (agent + 대시보드)

준비 (최초 1회):
```powershell
winget install shinchiro.mpv                 # C:\Program Files\MPV Player\mpv.exe
conda env create -f environment.yml
copy agent\.env.example agent\.env           # MQTT_HOST(파이 IP), MPV_PATH, BOARD_URL(보드 IP) 채우기
```

실행:
```powershell
conda activate air-dj
cd agent
python -m air_dj_agent
```
- 브라우저에 대시보드(`http://localhost:8080`)가 자동으로 열린다. 종료는 터미널에서 Ctrl+C (mpv도 같이 꺼진다).
- 음악은 정지 상태로 시작한다. 👌로 재생.

### 음악 폴더

- 대시보드 "지금 재생" 아래 **[폴더 선택]** 을 누르면 노트북에 폴더 선택 창이 뜬다. 고른 폴더의 오디오 파일이(하위 폴더 포함) 이름순으로 재생목록이 되고, 끝나면 처음부터 반복한다.
- 고른 폴더는 `agent/settings.json`에 저장돼 다음 실행 때도 쓴다. 처음 한 번은 `agent/.env`의 `MUSIC_DIR`가 기본값이다(비워 둬도 된다).
- 폴더에 곡을 추가/삭제했으면 **[새로고침]**. 재생목록이 처음 곡부터 다시 시작한다.

### 대시보드

- 카메라 영상 + 손 박스, 지금 인식된 제스처(최근 1초 기준, ●●●○○가 3개 차면 명령), 재생 중인 곡 정보, 최근 명령, 연결 상태.
- 보드 카메라 영상은 한 화면에만 나온다. 보드 자체 미리보기(`http://<보드 IP>`)와 동시에 열지 않는다.

## 라즈베리파이 5 (브로커 + receiver)

Raspberry Pi OS Lite 64-bit, Docker 설치 후:
```bash
git clone https://github.com/kimsegwang/air-dj.git ~/air-dj
cd ~/air-dj
cp .env.example .env          # SUPABASE_URL, SUPABASE_SECRET_KEY 채우기 (비워 두면 기록만 안 남는다)
docker compose up -d --build
docker compose logs -f receiver
```
- 재부팅해도 자동으로 다시 뜬다.
- `pi/` 코드를 바꾼 뒤 반영: `git pull && docker compose up -d --build receiver`
- Supabase 테이블은 `supabase/schema.sql`을 대시보드 SQL Editor에서 한 번 실행해 만든다.

## 보드 (XIAO ESP32S3 Sense)

ESP-IDF v5.5.6. Wi-Fi와 브로커 주소(`mqtt://<파이 IP>:1883`)는 `idf.py menuconfig` > air-dj에서 설정한다(`sdkconfig`에만 저장, 커밋하지 않음).
```powershell
cd firmware
idf.py build
idf.py -p COMx flash
```
자세한 개발 규칙과 실측 메모는 [CLAUDE.md](CLAUDE.md).

## 레포 구조

| 경로 | 내용 |
|---|---|
| `firmware/` | 보드 펌웨어 (카메라, 손 검출/제스처 분류, MQTT 발행, 개발용 웹 미리보기) |
| `pi/` | receiver (디바운스, 명령 발행, Supabase 저장), Dockerfile |
| `agent/` | 노트북 agent (mpv 제어, 대시보드) |
| `supabase/schema.sql` | 테이블 생성 SQL |
| `mosquitto/` | 브로커 설정 (LAN 전용, 인증 없음 — 포트를 인터넷에 열지 말 것) |
| `docker-compose.yml` | 파이에서 실행할 mosquitto + receiver |
