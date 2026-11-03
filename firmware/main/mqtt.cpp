#include "mqtt.hpp"

#include <atomic>
#include <cstring>

#include "esp_log.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

static const char *TAG = "mqtt";

static esp_mqtt_client_handle_t s_client;
static std::atomic<bool> s_connected{false};

// IDF 예제 protocols/mqtt/tcp 기반
static void event_handler(void *, esp_event_base_t, int32_t event_id, void *)
{
    switch (static_cast<esp_mqtt_event_id_t>(event_id)) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "connected");
        s_connected = true;
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "disconnected (client retries automatically)");
        s_connected = false;
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGW(TAG, "error event");
        break;
    default:
        break;
    }
}

void mqtt_start()
{
    if (strlen(CONFIG_AIRDJ_MQTT_BROKER_URI) == 0) {
        ESP_LOGW(TAG, "broker URI not set (menuconfig > air-dj), MQTT disabled");
        return;
    }
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = CONFIG_AIRDJ_MQTT_BROKER_URI;
    s_client = esp_mqtt_client_init(&cfg);
    if (!s_client) {
        ESP_LOGE(TAG, "esp_mqtt_client_init failed");
        return;
    }
    esp_mqtt_client_register_event(s_client, MQTT_EVENT_ANY, event_handler, nullptr);
    esp_mqtt_client_start(s_client);
}

void mqtt_publish(const char *topic, const char *payload)
{
    if (!s_client || !s_connected) {
        return;
    }
    if (esp_mqtt_client_publish(s_client, topic, payload, 0, 0, 0) < 0) {
        ESP_LOGW(TAG, "publish failed");
    }
}
