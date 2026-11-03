# air-dj

카메라 앞에서 손 제스처를 하면 노트북의 음악이 재생/정지/곡 넘김/볼륨 조절되는 프로젝트.

```
[XIAO ESP32S3 Sense] --air-dj/gesture--> [라즈베리파이 5: mosquitto + receiver] --air-dj/commands--> [노트북: agent → mpv → 스피커]
  카메라 + 손 제스처 인식(ESP-DL)                 디바운스 → 명령          \--> Supabase(기록)            + 대시보드(브라우저)
```

## 주요 기능

- **손 제스처로 음악 제어**: 재생 / 정지 / 다음 곡 / 이전 곡 / 볼륨 + / 볼륨 − (6가지, [제스처](#제스처) 참고)
- **온디바이스 인식**: 보드 안에서 사전 학습 모델로 손 검출과 제스처 분류. 파이로는 인식 결과(라벨·점수)만 보낸다
  (카메라 영상은 대시보드에 보여 주기 위해서만 집 LAN으로 스트리밍된다)
- **오작동 방지**: 순간적으로 잘못 인식된 프레임은 무시하고, 들고 있는 동안 명령은 한 번만 실행
- **대시보드 앱 창**: 카메라 영상과 손 박스, 지금 인식된 제스처, 재생 중인 곡(제목·아티스트·진행·볼륨·다음 곡), 최근 명령, 연결 상태를 한 화면에. 창을 닫으면 음악도 종료
- **음악 폴더 선택**: 대시보드에서 폴더를 고르면 하위 폴더까지 오디오 파일로 재생목록 구성, 다음 실행 때도 기억. 곡을 추가하면 [새로고침]
- **기록**: 모든 인식 프레임과 실행된 명령을 Supabase(Postgres)에 저장
- **자동 복구**: 브로커·보드·노트북 중 하나가 재시작돼도 자동으로 다시 연결. 파이 서비스는 재부팅 후 자동 시작

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

## 사용한 모델

직접 학습한 모델은 없다. Espressif가 ESP32-S3용으로 배포하는 **사전 학습 int8 모델 두 개**를 [ESP-DL](https://github.com/espressif/esp-dl)로 보드에서 실행한다.
모델 파일은 ESP-IDF 컴포넌트 매니저가 내려받아 펌웨어 플래시(rodata)에 함께 굽는다(레포에는 없음).

| 단계 | 컴포넌트 (버전) | 모델 | 입력 | 크기 |
|---|---|---|---|---|
| ① 손 검출 | `espressif/hand_detect` 0.2.1 | `espdet_pico_224_224_hand` (ESPDet-Pico 검출기) | 224×224 RGB | 약 0.5MB |
| ② 제스처 분류 | `espressif/hand_gesture_recognition` 0.2.1 | `mobilenetv2_0_5_128_128_gesture` (MobileNetV2 0.5×) | 128×128 RGB (손 영역을 잘라서) | 약 0.8MB |

- 추론 프레임워크: `espressif/esp-dl` 3.3.14 / 카메라: `espressif/esp32-camera` 2.1.8 (OV3660, QVGA 320×240 JPEG)
- 처리 흐름: JPEG 디코딩 → ① 손 위치(박스)와 검출 점수 → 손마다 잘라서 ② 제스처 분류 → 검출 점수가 가장 높은 손 하나를 MQTT로 발행
- 분류 라벨(11개): `one` `two` `three` `four` `five` `like` `ok` `call` `dislike` `no_gesture`, 손이 없으면 `no_hand`.
  이 중 6개를 명령에 쓴다(아래 표). `no_gesture`는 "손은 보이지만 아는 제스처가 아님"이다.
- 실측(실내, ESP32-S3 240MHz): 프레임당 약 185ms(약 5fps) = 디코딩 13 + 손 검출 171 + 분류 수 ms. 모델이 PSRAM 약 0.75MB 사용.
- 정확도 메모: ok/five/one/two/like는 안정적이고, dislike는 손 검출 점수가 낮아 느리다. 배경이 복잡하면 `no_gesture`가 많이 섞인다.
- 모델 정보 출처: `firmware/managed_components/espressif__hand_detect/README.md`, `.../espressif__hand_gesture_recognition/README.md` (빌드 후 생성)

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

## 처음 설치 (순서대로)

파이 IP가 있어야 보드와 노트북을 설정할 수 있으므로 **Supabase → 파이 → 보드 → 노트북** 순서로 한다.
세 기기는 **같은 와이파이(2.4GHz)** 에 있어야 한다(ESP32-S3는 5GHz를 지원하지 않는다).

### 준비물

- 하드웨어: XIAO ESP32S3 Sense(카메라 포함), 라즈베리파이 5 + microSD(16GB 이상), 윈도우 노트북(스피커)
- 노트북 소프트웨어: [Miniforge](https://github.com/conda-forge/miniforge)(conda), [ESP-IDF 설치 관리자 EIM](https://docs.espressif.com/projects/idf-im-ui/)(`winget install Espressif.eim`), Git, Microsoft Edge(윈도우 기본 포함)

### 1. Supabase (기록, 선택)

기록이 필요 없으면 건너뛴다(파이 `.env`를 비워 두면 기록만 안 남고 나머지는 동작한다).

1. [supabase.com](https://supabase.com)에서 프로젝트를 만든다.
2. 대시보드 **SQL Editor** → New query → [supabase/schema.sql](supabase/schema.sql) 내용을 붙여넣고 Run.
3. 두 값을 메모한다: **Project URL**(`https://<ref>.supabase.co`), **secret 키**(Settings > API Keys, `sb_secret_...`, 절대 공유 금지).

### 2. 라즈베리파이 5 (브로커 + receiver)

1. **SD 카드 굽기**: [Raspberry Pi Imager](https://www.raspberrypi.com/software/)에서 Raspberry Pi 5 → **Raspberry Pi OS Lite (64-bit)**.
   설정 편집에서 호스트 이름, 사용자 이름/비밀번호, **무선 LAN(위와 같은 와이파이)**, 시간대 Asia/Seoul, **SSH 사용**을 켠다.
2. 파이를 부팅하고(첫 부팅 1~2분) **파이 IP를 확인**한다. 공유기 관리 페이지의 접속 기기 목록이 가장 확실하다
   (`<호스트이름>.local`은 네트워크에 따라 안 될 수 있다). 공유기에서 이 IP를 고정(DHCP 예약)해 두면 나중에 설정을 다시 바꿀 일이 없다.
3. 노트북에서 SSH로 접속해 Docker와 레포를 설치한다:
   ```bash
   ssh <사용자>@<파이 IP>
   sudo apt-get update && sudo apt-get install -y git curl
   curl -fsSL https://get.docker.com | sudo sh        # Docker 공식 설치 스크립트
   sudo usermod -aG docker $USER && exit               # docker 그룹 반영을 위해 다시 접속
   ```
   ```bash
   ssh <사용자>@<파이 IP>
   git clone https://github.com/kimsegwang/air-dj.git ~/air-dj
   cd ~/air-dj
   cp .env.example .env && nano .env                   # 1번의 SUPABASE_URL, SUPABASE_SECRET_KEY (선택)
   docker compose up -d --build
   docker compose logs receiver                        # "MQTT connected" 가 보이면 성공
   ```
   재부팅해도 자동으로 다시 뜬다(`restart: unless-stopped`).

### 3. 보드 (XIAO ESP32S3 Sense)

1. EIM으로 **ESP-IDF v5.5.6**을 설치한다(다른 버전은 확인하지 않았다).
2. **conda가 꺼진 PowerShell**에서 ESP-IDF 환경을 켠다. EIM이 만든 활성화 스크립트를 dot-source 한다(경로는 설치 위치에 따라 다름):
   ```powershell
   conda deactivate                                     # conda가 켜져 있으면 빌드가 깨진다
   . 'C:\Espressif\tools\Microsoft.v5.5.6.PowerShell_profile.ps1'
   cd firmware
   idf.py set-target esp32s3                            # 최초 1회
   idf.py menuconfig
   ```
3. menuconfig > **air-dj** 에서 설정한다(`sdkconfig`에만 저장되고 커밋되지 않는다):
   - `Wi-Fi SSID` / `Wi-Fi password`: 위와 같은 2.4GHz 와이파이
   - `MQTT broker URI`: `mqtt://<파이 IP>:1883`
   - `Enable web preview`: 대시보드에서 카메라 영상을 보려면 켠다([보안 주의](#보안-주의) 참고)
4. 보드를 USB로 연결하고(장치 관리자에서 COM 번호 확인) 빌드·플래시:
   ```powershell
   idf.py build
   idf.py -p COMx flash
   ```
5. **보드 IP 확인**: 새 PowerShell에서 시리얼 로그를 읽어 `got ip: ...` 줄을 찾는다(공유기 관리 페이지에서도 확인 가능).
   ```powershell
   conda activate air-dj                                # 4번에서 만드는 환경. 아직 없으면 4번의 conda 줄을 먼저
   python tools/serial_read.py --port COMx --seconds 15
   ```
   파이에서 `docker compose logs mosquitto`에 `ESP32_...` 접속이 보이면 보드 → 파이 연결 성공.

### 4. 노트북 (agent + 대시보드)

```powershell
winget install shinchiro.mpv                            # C:\Program Files\MPV Player\mpv.exe
conda env create -f environment.yml                     # air-dj 환경 (최초 1회)
copy agent\.env.example agent\.env
notepad agent\.env
```
`agent/.env`에 채울 값:
| 변수 | 값 |
|---|---|
| `MQTT_HOST` | 파이 IP |
| `MPV_PATH` | `C:\Program Files\MPV Player\mpv.exe` |
| `BOARD_URL` | `http://<보드 IP>` (카메라 영상용) |
| `MUSIC_DIR` | 비워 둬도 된다(대시보드에서 고른다) |

### 5. 동작 확인

1. 노트북에서 agent 실행(아래 [평소 사용](#평소-사용)) → 대시보드 창이 뜬다.
2. 위쪽 표시가 **브로커·보드·카메라·플레이어** 모두 초록이면 연결 완료.
3. [폴더 선택]으로 음악 폴더를 고르고, 카메라 앞에서 👌 → 음악이 재생되면 끝.
4. (Supabase를 설정했다면) Table Editor > `gesture_commands`에 방금 명령이 쌓인다.

## 평소 사용

1. **파이와 보드 전원을 켠다.** 둘 다 알아서 와이파이에 붙고 서비스가 시작된다(1~2분).
2. **노트북에서 agent 실행**:
   ```powershell
   conda activate air-dj
   cd agent
   python -m air_dj_agent
   ```
3. 끝낼 때는 **대시보드 창을 닫는다**(또는 터미널에서 Ctrl+C). agent와 음악이 같이 꺼진다.
   파이와 보드는 켜 둬도 되고 그냥 전원을 빼도 된다.

- 음악은 정지 상태로 시작한다. 👌로 재생.
- 창을 닫아도 음악을 계속 틀고 싶으면 `agent/.env`에 `OPEN_BROWSER=tab`(일반 브라우저 탭, `http://localhost:8080`). 이때는 Ctrl+C로 끈다.

### 음악 폴더

- 대시보드 "지금 재생" 아래 **[폴더 선택]** 을 누르면 노트북에 폴더 선택 창이 뜬다. 고른 폴더의 오디오 파일이(하위 폴더 포함) 이름순으로 재생목록이 되고, 끝나면 처음부터 반복한다.
- 고른 폴더는 `agent/settings.json`에 저장돼 다음 실행 때도 쓴다. 처음 한 번은 `agent/.env`의 `MUSIC_DIR`가 기본값이다(비워 둬도 된다).
- 폴더에 곡을 추가/삭제했으면 **[새로고침]**. 재생목록이 처음 곡부터 다시 시작한다.

### 대시보드

- 카메라 영상 + 손 박스, 지금 인식된 제스처(최근 1초 기준, ●●●○○가 3개 차면 명령), 재생 중인 곡 정보, 최근 명령, 연결 상태.
- 보드 카메라 영상은 한 화면에만 나온다. 보드 자체 미리보기(`http://<보드 IP>`)와 동시에 열지 않는다.

## 코드나 설정을 바꿨을 때

| 바꾼 것 | 반영 방법 |
|---|---|
| `pi/` (receiver, 디바운스 규칙) | 파이에서 `cd ~/air-dj && git pull && docker compose up -d --build receiver` |
| `agent/` (플레이어, 대시보드) | 노트북에서 agent를 껐다 켠다 |
| `firmware/` 또는 보드 설정(와이파이, 파이 IP) | `idf.py menuconfig` → `idf.py build` → `idf.py -p COMx flash` |
| 파이 IP가 바뀜 | 보드 menuconfig의 브로커 URI와 `agent/.env`의 `MQTT_HOST`를 둘 다 바꾼다 |

자세한 개발 규칙과 실측 메모는 [CLAUDE.md](CLAUDE.md).

## 문제 해결

대시보드 위쪽 표시로 어디가 끊겼는지 본다.

| 증상 | 확인할 것 |
|---|---|
| **브로커** 빨강 | 파이 전원/와이파이, `agent/.env`의 `MQTT_HOST`가 파이 IP인지, 파이에서 `docker compose ps` |
| **보드** 빨강 | 보드 전원, 보드 와이파이(2.4GHz), 보드 menuconfig의 브로커 URI가 파이 IP인지(시리얼 로그 확인) |
| **카메라** 빨강 | `agent/.env`의 `BOARD_URL`, 보드 미리보기가 켜져 있는지, 다른 브라우저 창이 영상을 잡고 있지 않은지 |
| **플레이어** 빨강 | `MPV_PATH`가 맞는지, agent 터미널의 오류 메시지 |
| 다 초록인데 명령이 안 나감 | 배경을 깔끔하게, 손바닥을 카메라로, 50cm~1m. 같은 명령 반복은 손을 화면 밖으로 1초 뺐다가 |
| 소리가 안 남 | 재생목록이 비었는지(대시보드 "지금 재생"), 윈도우 볼륨, 👌로 재생했는지 |

## 보안 주의

집 와이파이에서 혼자 쓰는 것을 전제로 만들었다. 인터넷에서는 접근할 수 없다(공유기 포트포워딩을 하지 않는 한).

- **같은 와이파이 안에서는 인증 없이 접근된다.**
  - 카메라 영상: `http://<보드 IP>:81/stream`을 브라우저로 열면 누구나 볼 수 있다.
  - 브로커(1883): 누구나 접속해 명령 메시지를 보내 음악을 조작할 수 있다.
- **학교·카페 같은 공용 와이파이에서 쓰거나 시연할 때는** 보드 미리보기를 끈다:
  `idf.py menuconfig` > air-dj > `Enable web preview` 해제 후 빌드·플래시.
  대시보드의 카메라 칸만 비고 나머지(인식·명령·재생·기록)는 그대로 동작한다.
- Supabase로는 인식 결과(라벨·점수)와 명령만 간다. 영상·사진은 저장하지 않는다.
- Supabase secret 키는 파이 `.env`에만 둔다. 커밋하지 않는다.

## 레포 구조

| 경로 | 내용 |
|---|---|
| `firmware/` | 보드 펌웨어 (카메라, 손 검출/제스처 분류, MQTT 발행, 개발용 웹 미리보기) |
| `pi/` | receiver (디바운스, 명령 발행, Supabase 저장), Dockerfile |
| `agent/` | 노트북 agent (mpv 제어, 대시보드) |
| `supabase/schema.sql` | 테이블 생성 SQL |
| `mosquitto/` | 브로커 설정 (LAN 전용, 인증 없음 — 포트를 인터넷에 열지 말 것) |
| `docker-compose.yml` | 파이에서 실행할 mosquitto + receiver |
