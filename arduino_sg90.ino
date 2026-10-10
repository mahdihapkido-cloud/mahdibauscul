#include <Servo.h>

Servo myServo;

void setup() {
  Serial.begin(9600);
  myServo.attach(9);
  myServo.write(0);
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "PRESS") {
      myServo.write(90);
      delay(1000);
      myServo.write(0);
      delay(500);
      Serial.println("DONE");
    }
  }
}
