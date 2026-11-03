#include "preview.hpp"

#include <cstdio>
#include <cstring>

#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

static const char *TAG = "preview";

static SemaphoreHandle_t s_lock;
static uint8_t *s_jpeg;
static size_t s_jpeg_len;
static size_t s_jpeg_cap;
static uint32_t s_seq;
static char s_result[1024] = "{}";

static const char kIndexHtml[] = R"HTML(<!doctype html>
<html><head><meta charset="utf-8"><title>air-dj preview</title>
<style>
body{font-family:sans-serif;background:#111;color:#eee;margin:16px}
#wrap{position:relative;width:640px;height:480px}
#wrap img,#wrap canvas{position:absolute;left:0;top:0;width:640px;height:480px}
#info{font-family:monospace;margin-top:8px;white-space:pre}
</style></head><body>
<h3>air-dj preview</h3>
<div id="wrap"><img id="cam"><canvas id="ov" width="640" height="480"></canvas></div>
<div id="info">waiting...</div>
<script>
const cam=document.getElementById('cam'),ov=document.getElementById('ov'),ctx=ov.getContext('2d'),info=document.getElementById('info');
const streamUrl=`http://${location.hostname}:81/stream`;
// 스트림 서버는 한 번에 한 접속만 받으므로 실패하면 1초 뒤 다시 붙는다
cam.onerror=()=>setTimeout(()=>{cam.src=streamUrl+'?t='+Date.now()},1000);
cam.src=streamUrl;
async function tick(){
  try{
    const r=await (await fetch('/result',{cache:'no-store'})).json();
    ctx.clearRect(0,0,ov.width,ov.height);
    const sx=ov.width/(r.w||320),sy=ov.height/(r.h||240);
    ctx.lineWidth=3;ctx.font='20px sans-serif';
    for(const h of (r.hands||[])){
      const [x1,y1,x2,y2]=h.box;
      ctx.strokeStyle='#0f0';ctx.strokeRect(x1*sx,y1*sy,(x2-x1)*sx,(y2-y1)*sy);
      const t=`${h.label} ${h.score.toFixed(2)}`;
      ctx.fillStyle='rgba(0,0,0,.6)';ctx.fillRect(x1*sx,y1*sy-24,ctx.measureText(t).width+8,24);
      ctx.fillStyle='#0f0';ctx.fillText(t,x1*sx+4,y1*sy-6);
    }
    const hands=(r.hands||[]).map(h=>`${h.label} ${h.score.toFixed(2)} (det ${h.det.toFixed(2)})`).join(', ')||'no hand';
    info.textContent=`frame ${r.frame}  ${hands}\ndecode ${r.ms?.decode}ms  detect ${r.ms?.detect}ms  cls ${r.ms?.cls}ms  loop ${r.ms?.loop}ms`;
  }catch(e){info.textContent='error: '+e}
  setTimeout(tick,150);
}
tick();
</script></body></html>)HTML";

static esp_err_t index_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, kIndexHtml, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t result_handler(httpd_req_t *req)
{
    char buf[sizeof(s_result)];
    xSemaphoreTake(s_lock, portMAX_DELAY);
    memcpy(buf, s_result, sizeof(buf));
    xSemaphoreGive(s_lock);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return httpd_resp_sendstr(req, buf);
}

#define BOUNDARY "airdjframe"

static esp_err_t stream_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=" BOUNDARY);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    uint8_t *buf = nullptr;
    size_t cap = 0;
    uint32_t last_seq = 0;
    esp_err_t err = ESP_OK;

    while (err == ESP_OK) {
        size_t len = 0;
        xSemaphoreTake(s_lock, portMAX_DELAY);
        if (s_seq != last_seq && s_jpeg_len > 0) {
            if (cap < s_jpeg_len) {
                heap_caps_free(buf);
                cap = s_jpeg_len + s_jpeg_len / 4;
                buf = static_cast<uint8_t *>(heap_caps_malloc(cap, MALLOC_CAP_SPIRAM));
                if (!buf) {
                    cap = 0;
                    err = ESP_ERR_NO_MEM;
                }
            }
            if (buf) {
                memcpy(buf, s_jpeg, s_jpeg_len);
                len = s_jpeg_len;
                last_seq = s_seq;
            }
        }
        xSemaphoreGive(s_lock);

        if (err != ESP_OK) {
            break;
        }
        if (len == 0) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        char part[96];
        int n = snprintf(part, sizeof(part), "--" BOUNDARY "\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
                         (unsigned)len);
        err = httpd_resp_send_chunk(req, part, n);
        if (err == ESP_OK) {
            err = httpd_resp_send_chunk(req, reinterpret_cast<const char *>(buf), len);
        }
        if (err == ESP_OK) {
            err = httpd_resp_send_chunk(req, "\r\n", 2);
        }
    }
    heap_caps_free(buf);
    ESP_LOGI(TAG, "stream client left (%s)", esp_err_to_name(err));
    return ESP_OK;
}

void preview_start()
{
    s_lock = xSemaphoreCreateMutex();

    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t main_server = nullptr;
    if (httpd_start(&main_server, &cfg) == ESP_OK) {
        httpd_uri_t index = {.uri = "/", .method = HTTP_GET, .handler = index_handler, .user_ctx = nullptr};
        httpd_uri_t result = {.uri = "/result", .method = HTTP_GET, .handler = result_handler, .user_ctx = nullptr};
        httpd_register_uri_handler(main_server, &index);
        httpd_register_uri_handler(main_server, &result);
    } else {
        ESP_LOGE(TAG, "failed to start server on port %d", cfg.server_port);
    }

    httpd_config_t stream_cfg = HTTPD_DEFAULT_CONFIG();
    stream_cfg.server_port = 81;
    stream_cfg.ctrl_port = cfg.ctrl_port + 1;
    httpd_handle_t stream_server = nullptr;
    if (httpd_start(&stream_server, &stream_cfg) == ESP_OK) {
        httpd_uri_t stream = {.uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = nullptr};
        httpd_register_uri_handler(stream_server, &stream);
    } else {
        ESP_LOGE(TAG, "failed to start server on port %d", stream_cfg.server_port);
    }
}

void preview_set_frame(const uint8_t *jpeg, size_t len)
{
    if (!s_lock) {
        return;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_jpeg_cap < len) {
        heap_caps_free(s_jpeg);
        s_jpeg_cap = len + len / 4;
        s_jpeg = static_cast<uint8_t *>(heap_caps_malloc(s_jpeg_cap, MALLOC_CAP_SPIRAM));
        if (!s_jpeg) {
            s_jpeg_cap = 0;
        }
    }
    if (s_jpeg) {
        memcpy(s_jpeg, jpeg, len);
        s_jpeg_len = len;
        s_seq++;
    } else {
        s_jpeg_len = 0;
    }
    xSemaphoreGive(s_lock);
}

void preview_set_result(const char *json)
{
    if (!s_lock) {
        return;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    strlcpy(s_result, json, sizeof(s_result));
    xSemaphoreGive(s_lock);
}
