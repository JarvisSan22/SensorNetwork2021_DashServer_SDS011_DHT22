/*
 * SensorNet configurable node — ESP32
 *
 * ONE firmware for every node. All sensor drivers are compiled in; which ones
 * run is set per-node at provisioning time:
 *   - DHT22   (temp + humidity)       GPIO 4
 *   - PMS5003 (PM2.5 + PM10, laser)   UART2: TX->GPIO16(RX2), RX->GPIO17(TX2)
 *   - BMP280  (pressure)              I2C:   SDA GPIO21, SCL GPIO22 (addr 0x76)
 *   - SDS011  (PM2.5 + PM10, alt)     UART2  (shares pins with PMS5003)
 *
 * Provisioning (BOTH paths):
 *   1) Serial (primary): on an unprovisioned boot the node prints
 *      "AWAITING_CONFIG" on USB serial and accepts a one-line JSON config that
 *      the dashboard pushes right after flashing — no captive portal needed.
 *   2) Captive portal (fallback): if no serial config arrives, or the BOOT
 *      button is held at power-on, it opens the "SensorNet-Setup" WiFi AP.
 *
 * Config JSON (serial or saved to NVS):
 *   {"wifi_ssid":"..","wifi_pass":"..","server":"http://ip:8000",
 *    "node":"living-room","placement":"indoor",
 *    "dht":true,"pms":true,"bmp":false,"sds":false}
 */

#include <Arduino.h>
#if defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266HTTPClient.h>
  #include <WiFiClient.h>
  #include <LittleFS.h>          // config store (ESP8266 has no NVS/Preferences)
  #include <SoftwareSerial.h>    // PM sensor UART (ESP8266 has no Serial2)
#else
  #include <WiFi.h>
  #include <HTTPClient.h>
  #include <Preferences.h>       // NVS config store (ESP32)
#endif
#include <WiFiManager.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_BMP280.h>

// ---- Pins (keep in sync with the dashboard pin-setup modal) -----------------
#if defined(ESP8266)
  // NodeMCU / Wemos D-pin mapping. Avoids the boot-sensitive pins (GPIO0/2/15).
  #define DHT_PIN   14   // D5
  #define PMS_RX    12   // D6  <- PMS5003/SDS011 TX
  #define PMS_TX    13   // D7  -> PMS5003/SDS011 RX
  #define I2C_SDA   4    // D2
  #define I2C_SCL   5    // D1
  #define PORTAL_BUTTON 0    // D3 / FLASH button
  #define STATUS_LED_ACTIVE_LOW 1   // onboard LED is active-LOW on ESP8266
#else
  #define DHT_PIN   4
  #define PMS_RX    16   // <- PMS5003/SDS011 TX
  #define PMS_TX    17   // -> PMS5003/SDS011 RX
  #define I2C_SDA   21
  #define I2C_SCL   22
  #define PORTAL_BUTTON 0
  #define STATUS_LED_ACTIVE_LOW 0   // most ESP32 dev-board LEDs are active-HIGH
#endif
#define DHT_TYPE  DHT22
#define BMP_ADDR  0x76
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif
#define STATUS_LED LED_BUILTIN

DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_BMP280 bmp;

// PM sensor UART: hardware Serial2 on ESP32; software serial on ESP8266.
#if defined(ESP8266)
  SoftwareSerial pmSerial(PMS_RX, PMS_TX);
  #define PM_SERIAL pmSerial
#else
  #define PM_SERIAL Serial2
#endif

#if !defined(ESP8266)
  Preferences prefs;
#endif

// ---- Config -----------------------------------------------------------------
struct Config {
  String wifiSsid, wifiPass, server, node, placement = "indoor";
  bool dht = true, pms = false, bmp = false, sds = false;
} cfg;

bool bmpReady = false;
const unsigned long REPORT_INTERVAL_MS = 30000;
unsigned long lastReport = 0;

// ---- Config persistence -----------------------------------------------------
// ESP32 uses NVS (Preferences); ESP8266 has no NVS, so we store the same fields
// as a JSON file on LittleFS. Both paths are interchangeable to the rest of the
// firmware.
#if defined(ESP8266)
static const char *CONFIG_PATH = "/config.json";

static bool mountFS() {
  if (LittleFS.begin()) return true;
  return LittleFS.format() && LittleFS.begin();   // first-boot format
}

void loadConfig() {
  if (!mountFS()) return;
  File f = LittleFS.open(CONFIG_PATH, "r");
  if (!f) return;
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, f);
  f.close();
  if (err) return;
  cfg.wifiSsid  = doc["ssid"]   | "";
  cfg.wifiPass  = doc["pass"]   | "";
  cfg.server    = doc["server"] | "";
  cfg.node      = doc["node"]   | "";
  cfg.placement = doc["place"]  | "indoor";
  cfg.dht = doc["dht"] | true;
  cfg.pms = doc["pms"] | false;
  cfg.bmp = doc["bmp"] | false;
  cfg.sds = doc["sds"] | false;
}

void saveConfig() {
  if (!mountFS()) return;
  File f = LittleFS.open(CONFIG_PATH, "w");
  if (!f) return;
  JsonDocument doc;
  doc["ssid"]   = cfg.wifiSsid;
  doc["pass"]   = cfg.wifiPass;
  doc["server"] = cfg.server;
  doc["node"]   = cfg.node;
  doc["place"]  = cfg.placement;
  doc["dht"] = cfg.dht;
  doc["pms"] = cfg.pms;
  doc["bmp"] = cfg.bmp;
  doc["sds"] = cfg.sds;
  serializeJson(doc, f);
  f.close();
}
#else
void loadConfig() {
  prefs.begin("sensornet", true);
  cfg.wifiSsid  = prefs.getString("ssid", "");
  cfg.wifiPass  = prefs.getString("pass", "");
  cfg.server    = prefs.getString("server", "");
  cfg.node      = prefs.getString("node", "");
  cfg.placement = prefs.getString("place", "indoor");
  cfg.dht = prefs.getBool("dht", true);
  cfg.pms = prefs.getBool("pms", false);
  cfg.bmp = prefs.getBool("bmp", false);
  cfg.sds = prefs.getBool("sds", false);
  prefs.end();
}

void saveConfig() {
  prefs.begin("sensornet", false);
  prefs.putString("ssid", cfg.wifiSsid);
  prefs.putString("pass", cfg.wifiPass);
  prefs.putString("server", cfg.server);
  prefs.putString("node", cfg.node);
  prefs.putString("place", cfg.placement);
  prefs.putBool("dht", cfg.dht);
  prefs.putBool("pms", cfg.pms);
  prefs.putBool("bmp", cfg.bmp);
  prefs.putBool("sds", cfg.sds);
  prefs.end();
}
#endif

bool applyJson(const String &line) {
  JsonDocument doc;
  if (deserializeJson(doc, line)) return false;
  if (!doc["wifi_ssid"].is<const char *>()) return false;
  cfg.wifiSsid  = doc["wifi_ssid"].as<String>();
  cfg.wifiPass  = doc["wifi_pass"].as<String>();
  cfg.server    = doc["server"].as<String>();
  cfg.node      = doc["node"].as<String>();
  cfg.placement = doc["placement"] | "indoor";
  cfg.dht = doc["dht"] | true;
  cfg.pms = doc["pms"] | false;
  cfg.bmp = doc["bmp"] | false;
  cfg.sds = doc["sds"] | false;
  return true;
}

// ---- Provisioning -----------------------------------------------------------
// Returns true if serial-provisioned; false if it timed out (caller falls back).
bool serialProvision(unsigned long timeoutMs = 20000) {
  unsigned long start = millis();
  unsigned long lastPrompt = 0;
  while (millis() - start < timeoutMs) {
    if (millis() - lastPrompt > 1000) {
      Serial.println("AWAITING_CONFIG");   // dashboard waits for this marker
      lastPrompt = millis();
    }
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      line.trim();
      if (line.length() && applyJson(line)) {
        saveConfig();
        Serial.println("CONFIG_SAVED");
        delay(500);
        return true;
      }
    }
    delay(20);
  }
  return false;
}

void captivePortal() {
  WiFiManager wm;
  WiFiManagerParameter pServer("server", "Server URL (http://ip:8000)", cfg.server.c_str(), 64);
  WiFiManagerParameter pNode("node", "Node name", cfg.node.c_str(), 40);
  WiFiManagerParameter pPlace("place", "Placement (indoor/outdoor)", cfg.placement.c_str(), 12);
  WiFiManagerParameter pDht("dht", "DHT22 fitted (1/0)", cfg.dht ? "1" : "0", 2);
  WiFiManagerParameter pPms("pms", "PMS5003 fitted (1/0)", cfg.pms ? "1" : "0", 2);
  WiFiManagerParameter pBmp("bmp", "BMP280 fitted (1/0)", cfg.bmp ? "1" : "0", 2);
  for (auto *p : {&pServer, &pNode, &pPlace, &pDht, &pPms, &pBmp}) wm.addParameter(p);

  if (!wm.startConfigPortal("SensorNet-Setup")) ESP.restart();

  cfg.server = pServer.getValue();
  cfg.node = pNode.getValue();
  cfg.placement = String(pPlace.getValue()) == "outdoor" ? "outdoor" : "indoor";
  cfg.wifiSsid = WiFi.SSID();
  cfg.wifiPass = WiFi.psk();
  cfg.dht = String(pDht.getValue()) == "1";
  cfg.pms = String(pPms.getValue()) == "1";
  cfg.bmp = String(pBmp.getValue()) == "1";
  saveConfig();
}

// ---- Sensor reads -----------------------------------------------------------
// PMS5003: 32-byte frame, header 0x42 0x4D; PM2.5/PM10 atmospheric @ bytes 12..15
bool readPMS(float &pm25, float &pm10) {
  uint8_t buf[32];
  unsigned long start = millis();
  while (millis() - start < 1500) {
    if (PM_SERIAL.available() && PM_SERIAL.read() == 0x42) {
      if (PM_SERIAL.read() != 0x4D) continue;
      buf[0] = 0x42; buf[1] = 0x4D;
      if (PM_SERIAL.readBytes(buf + 2, 30) != 30) continue;
      uint16_t sum = 0;
      for (int i = 0; i < 30; i++) sum += buf[i];
      uint16_t chk = (buf[30] << 8) | buf[31];
      if (sum != chk) continue;
      pm25 = (buf[12] << 8) | buf[13];
      pm10 = (buf[14] << 8) | buf[15];
      return true;
    }
  }
  return false;
}

// SDS011: 10-byte frame, header 0xAA tail 0xAB
bool readSDS(float &pm25, float &pm10) {
  uint8_t buf[10];
  unsigned long start = millis();
  while (millis() - start < 1500) {
    if (PM_SERIAL.available() && PM_SERIAL.read() == 0xAA) {
      buf[0] = 0xAA;
      if (PM_SERIAL.readBytes(buf + 1, 9) == 9 && buf[1] == 0xC0 && buf[9] == 0xAB) {
        pm25 = (buf[2] | (buf[3] << 8)) / 10.0f;
        pm10 = (buf[4] | (buf[5] << 8)) / 10.0f;
        return true;
      }
    }
  }
  return false;
}

// ---- Status LED -------------------------------------------------------------
// 1 pulse  = readings sent OK;  2 pulses = error (no WiFi / failed POST).
// Onboard LED polarity differs by board (active-HIGH on ESP32, LOW on ESP8266).
void ledWrite(bool on) {
#if STATUS_LED_ACTIVE_LOW
  digitalWrite(STATUS_LED, on ? LOW : HIGH);
#else
  digitalWrite(STATUS_LED, on ? HIGH : LOW);
#endif
}

void ledPulse(int times, int onMs = 80, int offMs = 150) {
  for (int i = 0; i < times; i++) {
    ledWrite(true);
    delay(onMs);
    ledWrite(false);
    if (i < times - 1) delay(offMs);
  }
}

void postReadings() {
  if (cfg.server.isEmpty()) return;
  if (WiFi.status() != WL_CONNECTED) { ledPulse(2); return; }   // WiFi down -> error

  JsonDocument doc;
  doc["node"] = cfg.node;
  doc["placement"] = cfg.placement;
#if defined(ESP8266)
  doc["firmware"] = "node-esp8266-2.0";
#else
  doc["firmware"] = "node-esp32-2.0";
#endif
  JsonArray sensors = doc["sensor_types"].to<JsonArray>();
  JsonObject r = doc["readings"].to<JsonObject>();

  if (cfg.dht) {
    float t = dht.readTemperature(), h = dht.readHumidity();
    if (!isnan(t)) r["temperature_c"] = t;
    if (!isnan(h)) r["humidity_pct"] = h;
    sensors.add("DHT22");
  }
  if (cfg.bmp && bmpReady) {
    r["pressure_hpa"] = bmp.readPressure() / 100.0f;   // Pa -> hPa
    sensors.add("BMP280");
  }
  if (cfg.pms || cfg.sds) {
    float pm25, pm10;
    bool ok = cfg.pms ? readPMS(pm25, pm10) : readSDS(pm25, pm10);
    if (ok) {
      r["pm25"] = pm25;
      r["pm10"] = pm10;
      sensors.add(cfg.pms ? "PMS5003" : "SDS011");
    }
  }

  if (r.size() == 0) { Serial.println("No valid readings"); return; }

  String body;
  serializeJson(doc, body);
  HTTPClient http;
#if defined(ESP8266)
  WiFiClient client;   // ESP8266 HTTPClient::begin needs an explicit client
  http.begin(client, cfg.server + "/api/ingest");
#else
  http.begin(cfg.server + "/api/ingest");
#endif
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(body);
  Serial.printf("POST /api/ingest -> %d %s\n", code, body.c_str());
  http.end();

  ledPulse(code >= 200 && code < 300 ? 1 : 2);   // 1=sent OK, 2=server/HTTP error
}

void setup() {
  Serial.begin(115200);
  pinMode(PORTAL_BUTTON, INPUT_PULLUP);
  pinMode(STATUS_LED, OUTPUT);
  ledWrite(false);
  loadConfig();

  bool forcePortal = digitalRead(PORTAL_BUTTON) == LOW;

  if (cfg.wifiSsid.isEmpty() && !forcePortal) {
    // Unprovisioned: try serial first, fall back to captive portal.
    if (!serialProvision()) captivePortal();
  } else if (forcePortal) {
    captivePortal();
  }

  // Bring up sensors that are enabled.
  if (cfg.dht) dht.begin();
  if (cfg.pms || cfg.sds) {                    // both PMS5003 and SDS011 are 9600 8N1
#if defined(ESP8266)
    PM_SERIAL.begin(9600);                     // pins fixed in the constructor
#else
    PM_SERIAL.begin(9600, SERIAL_8N1, PMS_RX, PMS_TX);
#endif
  }
  if (cfg.bmp) {
    Wire.begin(I2C_SDA, I2C_SCL);
    bmpReady = bmp.begin(BMP_ADDR) || bmp.begin(0x77);
    if (!bmpReady) Serial.println("BMP280 not found");
  }

  // Connect WiFi using saved creds (portal path already connected).
  if (WiFi.status() != WL_CONNECTED && !cfg.wifiSsid.isEmpty()) {
    WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPass.c_str());
    for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  }
  Serial.printf("Node '%s' (%s) -> %s  dht=%d pms=%d bmp=%d sds=%d  wifi=%d\n",
                cfg.node.c_str(), cfg.placement.c_str(), cfg.server.c_str(),
                cfg.dht, cfg.pms, cfg.bmp, cfg.sds, WiFi.status() == WL_CONNECTED);

  // WiFi couldn't connect at boot -> double-flash so it's visible without serial.
  if (WiFi.status() != WL_CONNECTED) ledPulse(2);
}

void loop() {
  if (millis() - lastReport >= REPORT_INTERVAL_MS) {
    lastReport = millis();
    postReadings();
  }
}
