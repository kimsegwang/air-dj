#pragma once

// STA 모드로 접속하고 IP를 받을 때까지 최대 timeout_ms 기다린다. 끊기면 계속 재접속한다.
// SSID가 비어 있으면 아무것도 하지 않고 false.
bool wifi_connect(int timeout_ms);
