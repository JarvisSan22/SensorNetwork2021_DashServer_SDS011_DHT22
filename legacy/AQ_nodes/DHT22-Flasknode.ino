
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <DHT.h>


// Replace with your network credentials
const char* ssid = "";
const char* password = "";
String server= "/AQ_Plot_server_data_reciver upload ip";   
String nodename="DHT22";
String nodeloc = "";
String pingdata = "";
String url = "";
IPAddress ip;                    // the IP address of your shield
//unsigned long time;
#define DHTPIN 5     // Digital pin connected to the DHT sensor

// Uncomment the type of sensor in use:
//#define DHTTYPE    DHT11     // DHT 11
#define DHTTYPE    DHT22     // DHT 22 (AM2302)
//#define DHTTYPE    DHT21     // DHT 21 (AM2301)

DHT dht(DHTPIN, DHTTYPE);

// current temperature & humidity, updated in loop()
float t = 0.0;
float h = 0.0;

// Updates DHT readings every 10 seconds
const long interval = 10000; 
unsigned long previousMillis = 0;    // will store last time DHT was updated

// Sensors location name



void setup() {
  // put your setup code here, to run once:
   // Serial port for debugging purposes
  Serial.begin(115200);
  dht.begin();
  
  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println(".");
  }

  // Print ESP8266 Local IP Address
  Serial.println(WiFi.localIP());

}

void loop(){  
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    // save the last time you updated the DHT values
    previousMillis = currentMillis;
    // Read temperature as Celsius (the default)
    float newT = dht.readTemperature();
    // Read Humidity
    float newH = dht.readHumidity();
    if (isnan(newT)) {
      Serial.println("Failed to read from DHT sensor!");
    }
    else {
      //Start data to ping to serva
      String nodetime="test";
      url=String("http://"+server);
      pingdata=String(nodetime);
      
      t = newT;
      pingdata+=String(",DHT-T,");
      pingdata+=t;
      h = newH;
      pingdata+=String(",DHT-RH,");
      pingdata+=h;
   //   time = millis();
  //    Serial.println(time);
      Serial.println(t);
      Serial.println(h);
      
      ip=WiFi.localIP();
      pingdata+=String(",");
      pingdata+=ip.toString();
      Serial.println(ip);
      Serial.println(url+ "/data/"+nodename+"-"+nodeloc+"/"+pingdata);
      HTTPClient http;
      http.begin(url+ "/data/"+nodename+"-"+nodeloc+"/"+pingdata);
     // http.addHeader(Content-Type,);
     // http.POST(pingdata);
      http.GET();
     // http.writeToStream(&Serial);
      http.end();
    }
    
   
  }
}
