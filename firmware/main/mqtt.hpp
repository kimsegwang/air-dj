#pragma once

// 인식 결과를 매 프레임 MQTT로 보낸다 (QoS 0). 수신/디바운스는 파이가 한다.
inline constexpr const char *kGestureTopic = "air-dj/gesture";

// 브로커 URI가 비어 있으면 아무것도 하지 않는다. 접속/재접속은 백그라운드에서 진행된다.
void mqtt_start();
// 연결돼 있을 때만 보낸다. 연결 전/끊김 중의 프레임은 버린다.
void mqtt_publish(const char *topic, const char *payload);
