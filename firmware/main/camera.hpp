#pragma once
#include "esp_err.h"

// XIAO ESP32S3 Sense (OV3660) 카메라를 JPEG QVGA로 초기화하고 첫 프레임 몇 장을 버린다.
esp_err_t camera_init();
