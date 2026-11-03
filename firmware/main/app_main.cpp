#include "esp_heap_caps.h"
#include "esp_log.h"
#include "hand_detect.hpp"
#include "hand_gesture_recognition.hpp"

static const char *TAG = "air_dj";

extern "C" void app_main(void)
{
    ESP_LOGI(TAG, "PSRAM free: %u bytes", (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    // 빌드/링크 확인용: 모델 객체만 만든다. 카메라 연결은 다음 단계.
    HandDetect *hand_detect = new HandDetect();
    HandGestureRecognizer *recognizer = new HandGestureRecognizer();
    ESP_LOGI(TAG, "models created (detect=%p, recognizer=%p)", hand_detect, recognizer);

    ESP_LOGI(TAG, "PSRAM free: %u bytes", (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}
