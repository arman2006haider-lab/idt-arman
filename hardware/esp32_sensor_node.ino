/*
  Crop Guard - ESP32 Sensor Node
  --------------------------------
  Reads:
    - Soil moisture (capacitive/resistive analog sensor)
    - Rain intensity (analog rain drop sensor, inverted so higher = more rain)
    - Air temperature & humidity (DHT22)

  Sends a JSON payload via HTTP POST to the Crop Guard Flask server's
  /api/sensor-data endpoint every READING_INTERVAL_MS.

  Required libraries (Arduino Library Manager):
    - DHT sensor library (Adafruit)
    - ArduinoJson

  Wiring (adjust pins as needed):
    - Soil moisture sensor AOUT -> GPIO34 (ADC1_CH6)
    - Rain sensor AOUT          -> GPIO35 (ADC1_CH7)
    - DHT22 data pin            -> GPIO4 (with 10k pull-up to 3V3)
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ---- Configuration -------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Replace with your Flask server's address, e.g. http://192.168.1.50:5000
const char* SERVER_URL    = "http://192.168.1.50:5000/api/sensor-data";

// Device token shown on the farm's dashboard page after registration
const char* DEVICE_TOKEN  = "PUT_YOUR_FARM_DEVICE_TOKEN_HERE";
const char* DEVICE_ID     = "esp32-field-node-1";

const unsigned long READING_INTERVAL_MS = 5UL * 60UL * 1000UL; // every 5 minutes

// ---- Pins ------------------------------------------------------------------
#define SOIL_PIN  34
#define RAIN_PIN  35
#define DHT_PIN   4
#define DHT_TYPE  DHT22

DHT dht(DHT_PIN, DHT_TYPE);

// ---- Calibration -------------------------------------------------------
// Adjust these based on your sensor's dry/wet readings (raw ADC 0-4095)
const int SOIL_DRY_RAW = 3000;  // raw value in dry air
const int SOIL_WET_RAW = 1200;  // raw value fully submerged in water

const int RAIN_DRY_RAW = 4095;  // raw value when sensor is completely dry
const int RAIN_WET_RAW = 1500;  // raw value when sensor is heavily wet


void setup() {
  Serial.begin(115200);
  dht.begin();

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected, IP: " + WiFi.localIP().toString());
}


float readSoilMoisturePercent() {
  int raw = analogRead(SOIL_PIN);
  float pct = (float)(SOIL_DRY_RAW - raw) / (SOIL_DRY_RAW - SOIL_WET_RAW) * 100.0;
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

// Returns an approximate rain intensity in "mm/hr equivalent" (0-30)
float readRainIntensity() {
  int raw = analogRead(RAIN_PIN);
  float pct = (float)(RAIN_DRY_RAW - raw) / (RAIN_DRY_RAW - RAIN_WET_RAW) * 100.0;
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  // Map 0-100% sensor coverage to a rough 0-30 mm/hr scale
  return pct * 0.3;
}


void sendReading(float soil, float rain, float temp, float humidity) {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<256> doc;
  doc["device_token"] = DEVICE_TOKEN;
  doc["device_id"] = DEVICE_ID;
  doc["soil_moisture"] = soil;
  doc["rain_intensity"] = rain;
  doc["air_temperature"] = temp;
  doc["air_humidity"] = humidity;

  String body;
  serializeJson(doc, body);

  int httpCode = http.POST(body);
  Serial.printf("POST status: %d, body: %s\n", httpCode, body.c_str());
  http.end();
}


void loop() {
  float soil = readSoilMoisturePercent();
  float rain = readRainIntensity();
  float temp = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temp) || isnan(humidity)) {
    Serial.println("Failed to read DHT sensor, retrying next cycle.");
  } else {
    sendReading(soil, rain, temp, humidity);
  }

  delay(READING_INTERVAL_MS);
}
