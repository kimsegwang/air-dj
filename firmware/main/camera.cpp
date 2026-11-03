#include "camera.hpp"

#include "esp_camera.h"
#include "esp_log.h"
#include "sdkconfig.h"

static const char *TAG = "camera";

static constexpr int kDiscardFrames = 5;

// bool Kconfig가 n이면 매크로가 정의되지 않으므로 전처리기로 0/1을 만든다
#if CONFIG_AIRDJ_CAMERA_VFLIP
static constexpr int kVflip = 1;
#else
static constexpr int kVflip = 0;
#endif
#if CONFIG_AIRDJ_CAMERA_HMIRROR
static constexpr int kHmirror = 1;
#else
static constexpr int kHmirror = 0;
#endif

esp_err_t camera_init()
{
    camera_config_t config = {};
    // XIAO ESP32S3 Sense 핀 (CLAUDE.md 하드웨어 메모)
    config.pin_pwdn = -1;
    config.pin_reset = -1;
    config.pin_xclk = 10;
    config.pin_sccb_sda = 40;
    config.pin_sccb_scl = 39;
    config.pin_d7 = 48;
    config.pin_d6 = 11;
    config.pin_d5 = 12;
    config.pin_d4 = 14;
    config.pin_d3 = 16;
    config.pin_d2 = 18;
    config.pin_d1 = 17;
    config.pin_d0 = 15;
    config.pin_vsync = 38;
    config.pin_href = 47;
    config.pin_pclk = 13;

    config.xclk_freq_hz = 20000000;
    config.ledc_timer = LEDC_TIMER_0;
    config.ledc_channel = LEDC_CHANNEL_0;

    // JPEG: 미리보기는 그대로 보내고, 추론용으로만 RGB888로 디코딩한다
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_camera_init failed: %s", esp_err_to_name(err));
        return err;
    }

    sensor_t *s = esp_camera_sensor_get();
    ESP_LOGI(TAG, "sensor PID=0x%04x", s->id.PID);
    s->set_vflip(s, kVflip);
    s->set_hmirror(s, kHmirror);

    for (int i = 0; i < kDiscardFrames; i++) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb) {
            esp_camera_fb_return(fb);
        }
    }
    return ESP_OK;
}
