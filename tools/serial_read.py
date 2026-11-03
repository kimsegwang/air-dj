"""시리얼 로그를 N초 동안 읽고 종료한다 (idf.py monitor 대신, 비대화형).

    python tools/serial_read.py --port COM5 --seconds 15 [--reset]
"""

import argparse
import sys
import time

import serial


def hard_reset(port: serial.Serial) -> None:
    """esptool HardReset(uses_usb=True)과 같은 순서. DTR=False(IO0 HIGH)로 두고 RTS로 EN만 토글."""
    port.dtr = False
    port.rts = True   # EN -> LOW
    port.dtr = port.dtr  # Windows usbser.sys: RTS 변경을 실제로 보내기 위한 더미 DTR 설정 (esptool과 동일)
    time.sleep(0.2)
    port.rts = False  # EN -> HIGH
    port.dtr = port.dtr
    time.sleep(0.2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", required=True)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--reset", action="store_true", help="열자마자 보드를 리셋해 부팅 로그부터 받는다")
    args = parser.parse_args()

    port = serial.Serial()
    port.port = args.port
    port.baudrate = args.baud
    port.timeout = 0.2
    # 열 때 DTR/RTS가 켜지면 다운로드 모드로 들어가거나 리셋될 수 있으므로 먼저 끈다
    port.dtr = False
    port.rts = False
    port.open()

    try:
        if args.reset:
            hard_reset(port)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            data = port.read(4096)
            if data:
                sys.stdout.write(data.decode("utf-8", errors="replace"))
                sys.stdout.flush()
    except serial.SerialException as e:
        # USB-Serial-JTAG는 리셋 순간 포트가 잠깐 끊길 수 있다
        print(f"\n[serial_read] 포트 오류: {e}", file=sys.stderr)
        return 1
    finally:
        port.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
