#include <Adafruit_NeoPixel.h>
#include <MKRNB.h>
#include <PubSubClient.h>
#include <Servo.h>

Servo myservo;

//servo pin
#define servoPin 1

//led pin
#define PIN 3

Adafruit_NeoPixel strip = Adafruit_NeoPixel(36, PIN, NEO_GRB + NEO_KHZ800);

// initialize the library instance
NBClient client;
GPRS gprs;
NB nbAccess;

//connect the pubsub client
PubSubClient conn(client);

// Fill the dots one after the other with a color
void colorWipe(uint32_t c, uint8_t wait) {
  for(uint16_t i=0; i<strip.numPixels(); i++) {
    strip.setPixelColor(i, c);
    strip.show();
    delay(wait);
  }
}

void rainbowCycle(uint8_t wait) {
  uint16_t i, j;

  for(j=0; j<256*5; j++) { // 5 cycles of all colors on wheel
    for(i=0; i< strip.numPixels(); i++) {
      strip.setPixelColor(i, Wheel(((i * 256 / strip.numPixels()) + j) & 127));
    }
    strip.show();
    delay(wait);
  }
}

// Input a value 0 to 255 to get a color value.
// The colours are a transition r - g - b - back to r.
uint32_t Wheel(byte WheelPos) {
  WheelPos = 255 - WheelPos;
  if(WheelPos < 85) {
    return strip.Color(255 - WheelPos * 3, 0, WheelPos * 3);
  }
  if(WheelPos < 170) {
    WheelPos -= 85;
    return strip.Color(0, WheelPos * 3, 255 - WheelPos * 3);
  }
  WheelPos -= 170;
  return strip.Color(WheelPos * 3, 255 - WheelPos * 3, 0);
}

//for the callbacks from the broker
void callback(char* topic, byte* payload, unsigned int length) {
  char p[length + 1];
  memcpy(p, payload, length);
  p[length] = NULL;
  String message(p);

  if (message == "open") {
    colorWipe(strip.Color(0, 255, 0), 50); // Green    
  
    myservo.attach(servoPin);
    myservo.write(180);
    delay(1000);
    myservo.detach();
        
    rainbowCycle(5);
  } else if(message == "close"){
    colorWipe(strip.Color(255, 0, 0), 50); // Red    

    myservo.attach(servoPin);
    myservo.write(-180);
    delay(1000);
    myservo.detach();
          
    colorWipe(strip.Color(255, 255, 255), 50); // white
  } 
  
  Serial.println(message);
}

//connection and reconnection function 
void reconnect() {
    while (!conn.connected()) {
    
    // Attemp to connect
    if (conn.connect("smsafeClient")) {
      Serial.println("Connected");
      conn.subscribe("smsafe");
      conn.publish("online","smsafe");
    } else {
      Serial.print("Failed, rc=");
      Serial.print(conn.state());
      Serial.println(" try again in 2 seconds");
      // Wait 2 seconds before retrying
      delay(2000);
    }
  }
}

void setup() {  
  strip.begin();
  strip.show();
  strip.setBrightness(255);
  colorWipe(strip.Color(255, 0, 0), 10); // Red
  colorWipe(strip.Color(0, 255, 0), 10); // Blue
  colorWipe(strip.Color(0, 0, 255), 10); // Green  
  colorWipe(strip.Color(255, 255, 0), 10); // yellow  
  
  Serial.begin(9600);

  Serial.println("Warming up....");
  // connection state
  boolean connected = false;

  while (!connected) {
    if ((nbAccess.begin("") == NB_READY) &&
        (gprs.attachGPRS() == GPRS_READY)) {
        colorWipe(strip.Color(50, 50, 50), 10); // White
        connected = true;
    } else {
      Serial.println("Not connected");
      delay(1000);
    }
  }

  Serial.println("connecting...");

  conn.setServer("telstradev.com", 7337);
  conn.setCallback(callback);
}

void loop() {

  if (!conn.connected()) {
    reconnect();
  }
  conn.loop();
  
}
