#include <cstdio>
#include <vector>

#include "camera.hpp"
#include "dl_image_jpeg.hpp"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "hand_detect.hpp"
#include "hand_gesture_recognition.hpp"
#include "nvs_flash.h"
#include "preview.hpp"
#include "sdkconfig.h"
#include "wifi.hpp"

static const char *TAG = "air_dj";

static void init_nvs()
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
}

static int ms_since(int64_t t_us)
{
    return static_cast<int>((esp_timer_get_time() - t_us) / 1000);
}

extern "C" void app_main(void)
{
    init_nvs();
    ESP_ERROR_CHECK(camera_init());

    bool online = wifi_connect(15000);
#if CONFIG_AIRDJ_PREVIEW
    if (online) {
        preview_start();
        ESP_LOGI(TAG, "preview ready: open http://<board ip>/");
    }
#endif

    auto *detect = new HandDetect();
    auto *recognizer = new HandGestureRecognizer();
    ESP_LOGI(TAG, "PSRAM free before first inference: %u", (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    char json[1024];
    for (uint32_t frame = 1;; frame++) {
        int64_t t_loop = esp_timer_get_time();

        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGW(TAG, "camera frame timeout");
            continue;
        }
        if (online) {
            preview_set_frame(fb->buf, fb->len);
        }
        int64_t t = esp_timer_get_time();
        dl::image::jpeg_img_t jpeg = {.data = fb->buf, .data_len = fb->len};
        dl::image::img_t img = dl::image::sw_decode_jpeg(jpeg, dl::image::DL_IMAGE_PIX_TYPE_RGB888);
        esp_camera_fb_return(fb);
        int decode_ms = ms_since(t);
        if (!img.data) {
            ESP_LOGW(TAG, "jpeg decode failed");
            continue;
        }

        t = esp_timer_get_time();
        std::list<dl::detect::result_t> &hands = detect->run(img);
        int detect_ms = ms_since(t);

        t = esp_timer_get_time();
        std::vector<dl::cls::result_t> gestures;
        if (!hands.empty()) {
            gestures = recognizer->recognize(img, hands);
        }
        int cls_ms = ms_since(t);
        heap_caps_free(img.data);
        int loop_ms = ms_since(t_loop);

        if (frame == 1) {
            ESP_LOGI(TAG, "PSRAM free after first inference: %u", (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
        }

        // 결과 JSON (미리보기용) + 로그 한 줄
        int n = snprintf(json, sizeof(json), "{\"frame\":%lu,\"w\":%u,\"h\":%u,\"hands\":[", (unsigned long)frame,
                         img.width, img.height);
        size_t i = 0;
        for (const auto &hand : hands) {
            if (i >= gestures.size() || n >= (int)sizeof(json) - 160) {
                break;
            }
            const auto &g = gestures[i];
            n += snprintf(json + n, sizeof(json) - n,
                          "%s{\"label\":\"%s\",\"score\":%.3f,\"det\":%.3f,\"box\":[%d,%d,%d,%d]}", i ? "," : "",
                          g.cat_name, g.score, hand.score, hand.box[0], hand.box[1], hand.box[2], hand.box[3]);
            ESP_LOGI(TAG, "frame %lu: %s %.2f (det %.2f box %d,%d,%d,%d) decode %d detect %d cls %d loop %d ms",
                     (unsigned long)frame, g.cat_name, g.score, hand.score, hand.box[0], hand.box[1], hand.box[2],
                     hand.box[3], decode_ms, detect_ms, cls_ms, loop_ms);
            i++;
        }
        if (hands.empty()) {
            ESP_LOGI(TAG, "frame %lu: no hand  decode %d detect %d loop %d ms", (unsigned long)frame, decode_ms,
                     detect_ms, loop_ms);
        }
        snprintf(json + n, sizeof(json) - n, "],\"ms\":{\"decode\":%d,\"detect\":%d,\"cls\":%d,\"loop\":%d}}",
                 decode_ms, detect_ms, cls_ms, loop_ms);
        if (online) {
            preview_set_result(json);
        }
        vTaskDelay(1);  // IDLE 태스크가 돌 수 있게 양보 (태스크 워치독)
    }
}
