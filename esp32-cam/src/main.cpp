#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SD_MMC.h>
#include <esp_camera.h>
#include <img_converters.h>
#include <camera_config.h>

// AI Thinker / diymore ESP32-CAM with OV2640, not ESP32-S3 USB cameras.
static WebServer server(80);
static bool cameraReady = false;
static bool sdReady = false;
static String cameraError;
static constexpr size_t MAX_JPEG = 2 * 1024 * 1024;
static constexpr size_t MAX_THUMB = 32768;

static void fail(int status, const String &message) {
    Serial.println(message);
    server.send(status, "text/plain", message);
}

static String photoPath(const String &id, const char *suffix) {
    return "/photos/" + id + suffix;
}

static bool validId(const String &id) {
    if (id.length() != 16) return false;
    for (char c : id) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

static bool mountCard() {
    // One-bit SD avoids the white flash LED on GPIO4. Never format the card.
    if (!SD_MMC.begin("/sdcard", true) || SD_MMC.cardType() == CARD_NONE) return false;
    return SD_MMC.exists("/photos") || SD_MMC.mkdir("/photos");
}

static bool writeAtomic(const String &path, const uint8_t *data, size_t length,
                        uint8_t orientation = 1) {
    uint8_t exif[] = {
        0xff, 0xe1, 0x00, 0x22, 'E', 'x', 'i', 'f', 0, 0,
        'I', 'I', 0x2a, 0, 8, 0, 0, 0, 1, 0,
        0x12, 1, 3, 0, 1, 0, 0, 0, orientation, 0, 0, 0, 0, 0, 0, 0
    };
    String temporary = path + ".tmp";
    File file = SD_MMC.open(temporary, FILE_WRITE);
    if (!file) return false;
    if (length < 2 || data[0] != 0xff || data[1] != 0xd8) {
        file.close();
        return false;
    }
    size_t written = file.write(data, 2);
    written += file.write(exif, sizeof(exif));
    written += file.write(data + 2, length - 2);
    file.flush();
    file.close();
    if (written != length + sizeof(exif)) return false;
    return SD_MMC.rename(temporary, path);
}

static bool isUXGA(const uint8_t *jpeg, size_t size) {
    if (size < 4 || jpeg[0] != 0xff || jpeg[1] != 0xd8 ||
        jpeg[size - 2] != 0xff || jpeg[size - 1] != 0xd9) return false;
    size_t offset = 2;
    while (offset + 4 <= size) {
        if (jpeg[offset] != 0xff) return false;
        uint8_t marker = jpeg[offset + 1];
        if (marker == 0xff) {
            offset++;
            continue;
        }
        size_t length = (jpeg[offset + 2] << 8) | jpeg[offset + 3];
        if (length < 2 || offset + length + 2 > size) return false;
        if (marker == 0xc0) {
            return length >= 8 &&
                ((jpeg[offset + 5] << 8) | jpeg[offset + 6]) == 1200 &&
                ((jpeg[offset + 7] << 8) | jpeg[offset + 8]) == 1600;
        }
        if (marker == 0xda) return false;
        offset += length + 2;
    }
    return false;
}

static camera_fb_t *freshFrame(framesize_t size, int quality, int discard) {
    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor->set_framesize(sensor, size) != 0 ||
        sensor->set_quality(sensor, quality) != 0) return nullptr;
    for (int i = 0; i < discard; i++) {
        camera_fb_t *old = esp_camera_fb_get();
        if (!old) return nullptr;
        esp_camera_fb_return(old);
        delay(30);
    }
    return esp_camera_fb_get();
}

static bool makeThumbnail(const String &id) {
    // Decode the file read back from SD, not a subsequent live camera frame.
    File file = SD_MMC.open(photoPath(id, ".jpg"), FILE_READ);
    if (!file || file.size() < 4 || file.size() > MAX_JPEG) return false;
    size_t size = file.size();
    uint8_t *jpeg = static_cast<uint8_t *>(ps_malloc(size));
    uint8_t *rgb = static_cast<uint8_t *>(ps_malloc(200 * 150 * 2));
    if (!jpeg || !rgb) {
        free(jpeg);
        free(rgb);
        return false;
    }
    bool ok = file.read(jpeg, size) == size;
    file.close();
    uint8_t orientation = 1;
    if (ok && size >= 38 && jpeg[2] == 0xff && jpeg[3] == 0xe1 &&
        jpeg[4] == 0 && jpeg[5] == 0x22 &&
        memcmp(jpeg + 6, "Exif\0\0II", 8) == 0) {
        orientation = jpeg[30];
    }
    if (ok) ok = isUXGA(jpeg, size) && jpg2rgb565(jpeg, size, rgb, JPG_SCALE_8X);
    free(jpeg);
    uint8_t *thumb = nullptr;
    size_t length = 0;
    if (ok) {
        // The pinned decoder emits LE RGB565; the JPEG encoder expects BE.
        for (size_t i = 0; i < 200 * 150 * 2; i += 2) {
            uint8_t low = rgb[i];
            rgb[i] = rgb[i + 1];
            rgb[i + 1] = low;
        }
        ok = fmt2jpg(rgb, 200 * 150 * 2, 200, 150, PIXFORMAT_RGB565,
                     75, &thumb, &length);
    }
    free(rgb);
    if (ok) ok = length + 36 <= MAX_THUMB &&
                 writeAtomic(photoPath(id, ".thumb.jpg"), thumb, length, orientation);
    free(thumb);
    return ok;
}

static void capture() {
    String id = server.arg("id");
    if (!validId(id)) return fail(400, "Invalid capture ID");
    String rotation = server.hasArg("rotation") ? server.arg("rotation") : "0";
    if (rotation != "0" && rotation != "90" && rotation != "180" && rotation != "270") {
        return fail(400, "Rotation must be 0, 90, 180 or 270");
    }
    uint8_t orientation = rotation == "90" ? 6 : rotation == "180" ? 3 :
                          rotation == "270" ? 8 : 1;
    if (!cameraReady) return fail(503, cameraError);
    if (!sdReady) {
        SD_MMC.end();
        sdReady = mountCard();
    }
    if (!sdReady) return fail(507, "SD card unavailable: insert a FAT32 card and retry");
    String path = photoPath(id, ".jpg");
    // Retrying a lost response with the same ID must not take a second photo.
    if (!SD_MMC.exists(path)) {
        camera_fb_t *frame = freshFrame(FRAMESIZE_UXGA, 10, 3);
        bool ok = frame && frame->format == PIXFORMAT_JPEG &&
                  frame->width == 1600 && frame->height == 1200 &&
                  frame->len + 36 <= MAX_JPEG && isUXGA(frame->buf, frame->len);
        if (ok) ok = writeAtomic(path, frame->buf, frame->len, orientation);
        if (frame) esp_camera_fb_return(frame);
        sensor_t *sensor = esp_camera_sensor_get();
        sensor->set_framesize(sensor, FRAMESIZE_QVGA);
        sensor->set_quality(sensor, 18);
        if (!ok) return fail(507, "Full-resolution capture/save failed; check SD space");
        Serial.printf("Saved %s (1600x1200)\n", path.c_str());
    }
    if (!SD_MMC.exists(photoPath(id, ".thumb.jpg")) && !makeThumbnail(id)) {
        return fail(500, "Photo is on SD; thumbnail failed. Retry the same capture");
    }
    server.send(200, "application/json",
                "{\"id\":\"" + id + "\",\"width\":1600,\"height\":1200,\"saved\":true}");
}

static void preview() {
    if (!cameraReady) return fail(503, cameraError);
    camera_fb_t *frame = freshFrame(FRAMESIZE_QVGA, 18, 1);
    if (!frame) return fail(503, "Camera frame unavailable");
    if (frame->len > 65536) {
        esp_camera_fb_return(frame);
        return fail(503, "Preview too large");
    }
    server.sendHeader("Cache-Control", "no-store");
    server.setContentLength(frame->len);
    server.send(200, "image/jpeg", "");
    server.sendContent(reinterpret_cast<const char *>(frame->buf), frame->len);
    esp_camera_fb_return(frame);
}

static void thumbnail() {
    String id = server.arg("id");
    if (!validId(id)) return fail(400, "Invalid capture ID");
    File file = SD_MMC.open(photoPath(id, ".thumb.jpg"), FILE_READ);
    if (!file) return fail(404, "Saved thumbnail unavailable");
    server.streamFile(file, "image/jpeg");
    file.close();
}

static void original() {
    String id = server.arg("id");
    if (!validId(id)) return fail(400, "Invalid capture ID");
    File file = SD_MMC.open(photoPath(id, ".jpg"), FILE_READ);
    if (!file) return fail(404, "Original photo unavailable");
    server.streamFile(file, "image/jpeg");
    file.close();
}

static void setupCamera() {
    if (!psramFound()) {
        cameraError = "PSRAM unavailable; cannot safely capture UXGA";
        return;
    }
    camera_config_t config = {};
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = 5;
    config.pin_d1 = 18;
    config.pin_d2 = 19;
    config.pin_d3 = 21;
    config.pin_d4 = 36;
    config.pin_d5 = 39;
    config.pin_d6 = 34;
    config.pin_d7 = 35;
    config.pin_xclk = 0;
    config.pin_pclk = 22;
    config.pin_vsync = 25;
    config.pin_href = 23;
    config.pin_sccb_sda = 26;
    config.pin_sccb_scl = 27;
    config.pin_pwdn = 32;
    config.pin_reset = -1;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_UXGA;
    config.jpeg_quality = 10;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    esp_err_t result = esp_camera_init(&config);
    if (result != ESP_OK) {
        cameraError = "Camera initialization failed: " + String(result);
        return;
    }
    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor->id.PID != OV2640_PID) {
        cameraError = "Unsupported sensor: this firmware requires OV2640";
        esp_camera_deinit();
        return;
    }
    cameraReady = true;
    sensor->set_framesize(sensor, FRAMESIZE_QVGA);
    sensor->set_quality(sensor, 18);
}

void setup() {
    Serial.begin(115200);
    pinMode(4, OUTPUT);
    digitalWrite(4, LOW);
    setupCamera();
    sdReady = mountCard();
    WiFi.mode(WIFI_AP);
    WiFi.setSleep(false);
    if (!WiFi.softAP(CAMERA_SSID, CAMERA_PASSWORD, 6, false, 1)) {
        Serial.println("Wi-Fi AP initialization failed");
        return;
    }
    server.on("/status", HTTP_GET, []() {
        server.send(200, "application/json",
            String("{\"protocol\":1,\"camera\":") + (cameraReady ? "true" : "false") +
            ",\"sd\":" + (sdReady ? "true" : "false") +
            ",\"error\":\"" + cameraError + "\"" +
            ",\"sensor\":\"OV2640\",\"width\":1600,\"height\":1200}");
    });
    server.on("/preview", HTTP_GET, preview);
    server.on("/capture", HTTP_POST, capture);
    server.on("/thumbnail", HTTP_GET, thumbnail);
    server.on("/photo", HTTP_GET, original);
    server.onNotFound([]() { fail(404, "Unknown camera endpoint"); });
    server.begin();
    Serial.printf("Badge camera ready: camera=%d SD=%d IP=%s\n",
                  cameraReady, sdReady, WiFi.softAPIP().toString().c_str());
    if (!cameraReady) Serial.println(cameraError);
}

void loop() {
    server.handleClient();
    delay(2);
}
