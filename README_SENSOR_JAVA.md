# DMSTracker - Java + ESP32 Sensor Integration

## Added modules

- `/java/DMSDataClient.java` - Java HTTP client for testing sensor-to-Flask communication.
- `/iot/esp32/DMSTrackerSensor.ino` - ESP32 Wi-Fi/API example.
- `/sensor` - student sensor dashboard.
- `/api/sensor-data` - Flask endpoint for sensor readings.
- SQLite `sensor_readings` table with user ownership.

## Java test

Start Flask first, log in, then use the Java client as a development integration example. The current API requires an authenticated browser session, so a production standalone Java client should use a dedicated authentication/token design rather than bypassing authentication.

## Hardware

The ESP32 sketch uses demo values. Replace them with readings from your actual sensor libraries, such as MAX30102 or DHT11/DHT22.

## Safety

This is an educational student project. Sensor values must not be presented as medical diagnosis or emergency monitoring.


## Fast sensor verification

1. Start Flask:
   `python app.py`
2. Log in to DMSTracker.
3. Open **Sensors**.
4. Click **Send Demo Sensor Reading**.
5. The page should show a new reading immediately.
6. For Java testing, open **Account → Sensor Device Connection**, generate a device token, then set:
   `$env:DMS_SENSOR_TOKEN = "YOUR_TOKEN_HERE"`
7. Compile and run:
   `javac DMSDataClient.java`
   `java DMSDataClient`

The Java and ESP32 clients use the device token instead of the user's password.
This keeps account credentials out of sensor-device code.

