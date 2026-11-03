#pragma once
#include <cstddef>
#include <cstdint>

// 개발용 웹 미리보기.
//   포트 80: /       페이지 (영상 위에 손 박스/라벨 오버레이)
//            /result 최신 인식 결과 JSON
//   포트 81: /stream MJPEG 스트림
// httpd는 핸들러를 한 번에 하나씩 처리하므로 스트림은 별도 서버로 띄운다.
void preview_start();
void preview_set_frame(const uint8_t *jpeg, size_t len);
void preview_set_result(const char *json);
