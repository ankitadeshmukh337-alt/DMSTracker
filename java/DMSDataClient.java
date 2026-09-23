// DMSTracker Java Sensor Test Client
// Sends educational sensor readings to the Flask API using a secure device token.
// Replace demo values with real sensor values when hardware is connected.

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class DMSDataClient {

    public static void main(String[] args) throws IOException, InterruptedException {

        // Use the local Flask server during development.
        String apiUrl = "http://127.0.0.1:5000/api/sensor-data";

        // Paste the token generated from DMSTracker -> Account -> Sensor Device Connection.
        String deviceToken = System.getenv("DMS_SENSOR_TOKEN");
        if (deviceToken == null || deviceToken.isBlank()) {
            System.out.println("ERROR: DMS_SENSOR_TOKEN is not set.");
            System.out.println("Open DMSTracker -> Account -> Sensor Device Connection,");
            System.out.println("generate a token, then set it in this PowerShell:");
            System.out.println("$env:DMS_SENSOR_TOKEN = \"YOUR_TOKEN_HERE\"");
            return;
        }

        // Demo values for testing the software integration.
        double heartRate = 72.0;
        double spo2 = 98.0;
        double temperature = 36.7;

        String json = String.format(
            "{\"heart_rate\":%.1f,\"spo2\":%.1f,\"temperature\":%.1f}",
            heartRate, spo2, temperature
        );

        HttpClient client = HttpClient.newHttpClient();

        // Build a POST request containing JSON sensor data and the device token.
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(apiUrl))
            .header("Content-Type", "application/json")
            .header("X-Device-Token", deviceToken)
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build();

        HttpResponse<String> response =
            client.send(request, HttpResponse.BodyHandlers.ofString());

        System.out.println("HTTP Status: " + response.statusCode());
        System.out.println("Server Response: " + response.body());

        if (response.statusCode() == 200) {
            System.out.println("Sensor test successful. Refresh the DMSTracker Sensors page.");
        } else if (response.statusCode() == 401) {
            System.out.println("Authentication failed. Generate a new token in Account.");
        }
    }
}
