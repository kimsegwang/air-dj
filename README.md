# air-dj

카메라 앞에서 손 제스처를 하면 노트북의 음악이 재생/정지/곡 넘김/볼륨 조절되는 프로젝트.

```
[XIAO ESP32S3 Sense] --air-dj/gesture--> [라즈베리파이 5: mosquitto + receiver] --air-dj/commands--> [노트북: agent → mpv → 스피커]
  카메라 + 손 제스처 인식(ESP-DL)                 디바운스 → 명령          \--> Supabase(기록)            + 대시보드(브라우저)
```

## 역할 분담

**보드는 인식, 파이는 판단·중계·기록, 노트북은 재생.** 각 부분을 다른 부분과 상관없이 바꿀 수 있게 나눴다.

| 구성 | 하는 일 | 이렇게 둔 이유 |
|---|---|---|
| **보드** (XIAO ESP32S3 Sense) | 카메라로 손을 찾고 제스처를 분류(사전 학습 모델, 온디바이스)해 매 프레임(약 5fps) "지금 보이는 것"을 MQTT로 보낸다 | 영상을 네트워크로 보내지 않고 보드 안에서 인식한다. 프레임당 약 185ms 중 171ms를 손 검출에 써서 다른 일을 할 여유가 적다 |
| **라즈베리파이 5** | ① MQTT 브로커(mosquitto) ② receiver: 프레임을 모아 명령을 결정(디바운스 — 최근 5프레임 중 3번 같은 제스처면 한 번만 발행) ③ 모든 프레임과 명령을 Supabase에 기록 | 항상 켜져 있는 고정 주소라 보드·노트북이 꺼졌다 켜져도 서로 찾는다. 판단 규칙은 보드를 다시 플래시하지 않고 `git pull`로 바꾼다. DB 비밀 키를 파이 한 곳에만 둔다 |
| **노트북** | agent가 명령을 받아 mpv로 음악을 재생하고, 대시보드(카메라·인식·재생 정보)를 띄운다 | 스피커와 음악 파일이 노트북에 있다. 파이에는 오디오 출력이 없다 |

- 보드는 판단하지 않고, 노트북은 제스처를 모른다. 파이만 "어떤 제스처가 어떤 명령인지"를 안다.
- 보드와 노트북은 DB에 직접 접속하지 않는다.
- 참고: 음악이 노트북에서 나오므로, 기능만 보면 노트북이 브로커와 receiver까지 맡아도 동작한다. 파이를 따로 둔 덕분에
  노트북이 꺼져 있어도 기록이 쌓이고, 재생 장치를 바꿔도(예: 다른 스피커 기기) 파이 쪽은 그대로 쓸 수 있다.

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
- 대시보드가 주소창 없는 앱 창으로 열린다(Edge). **이 창을 닫으면 agent와 음악도 같이 꺼진다.** 터미널에서 Ctrl+C로 꺼도 된다.
- 창을 닫아도 음악을 계속 틀고 싶으면 `agent/.env`에 `OPEN_BROWSER=tab`(일반 브라우저 탭, `http://localhost:8080`).
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
