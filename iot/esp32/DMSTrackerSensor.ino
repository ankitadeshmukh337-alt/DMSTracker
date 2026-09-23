// DMSTracker ESP32 Sensor Example
// Educational example for sending readings to the Flask API.
// Replace the demo values with real sensor library readings.

#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Replace with your local computer IP or deployed HTTPS API endpoint.
const char* API_URL = "http://YOUR_SERVER_IP:5000/api/sensor-data";

// Paste the token generated from DMSTracker -> Account -> Sensor Device Connection.
const char* DEVICE_TOKEN = "PASTE_YOUR_SENSOR_DEVICE_TOKEN_HERE";

void setup() {
  Serial.begin(115200);

  // Connect the ESP32 to Wi-Fi.
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWi-Fi connected");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {

    // Demo values: replace these with actual sensor readings.
    float heartRate = 72.0;
    float spo2 = 98.0;
    float temperature = 36.7;

    HTTPClient http;
    http.begin(API_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Token", DEVICE_TOKEN);

    String json =
      "{\"heart_rate\":" + String(heartRate, 1) +
      ",\"spo2\":" + String(spo2, 1) +
      ",\"temperature\":" + String(temperature, 1) + "}";

    // Send the JSON payload to the Flask API.
    int statusCode = http.POST(json);

    Serial.print("API status: ");
    Serial.println(statusCode);

    http.end();
  }

  delay(60000);
}
