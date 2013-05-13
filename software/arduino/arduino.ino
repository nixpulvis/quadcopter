#include <Servo.h>
#include "motor.h"

Motor motor_a(9);  // Arduino pin 9.
Motor motor_b(10); // Arduino pin 10.

void setup() {
  Serial.begin(9600);

  // Initialize the motors before anything else. For the ESCs to
  // operate the arduino must be attached and sending 0% power when
  // the ESCs gain power. Therefor the ESCs must NOT have power
  // during this part of the setup.
  motor_a.initialize();
  motor_b.initialize();

  // Now the ESCs may have power.
}

int incomingByte = 0;   // for incoming serial data

void loop() {
  if (Serial.available() > 0) {
    // read the incoming byte:
    incomingByte = Serial.read();

    if (incomingByte == 96) { // key: "`"
      Serial.println("attach");
      motor_a.attach();
      motor_b.attach();

    } else if (incomingByte == 45) { // key: "-"
      Serial.println("detach");
      motor_a.detach();
      motor_b.detach();

    } else if (incomingByte == 48) {
      Serial.println(0);
      motor_a.write(0);
      motor_b.write(0);

    } else if (incomingByte == 49) {
      Serial.println(1);
      motor_a.write(1);
      motor_b.write(1);

    } else if (incomingByte == 50) {
      Serial.println(13);
      motor_a.write(13);
      motor_b.write(13);

    } else if (incomingByte == 51) {
      Serial.println(25);
      motor_a.write(25);
      motor_b.write(25);

    } else if (incomingByte == 52) {
      Serial.println(37);
      motor_a.write(37);
      motor_b.write(37);

    } else if (incomingByte == 53) {
      Serial.println(49);
      motor_a.write(49);
      motor_b.write(49);

    } else if (incomingByte == 54) {
      Serial.println(61);
      motor_a.write(61);
      motor_b.write(61);

    } else if (incomingByte == 55) {
      Serial.println(73);
      motor_a.write(73);
      motor_b.write(73);

    } else if (incomingByte == 56) {
      Serial.println(85);
      motor_a.write(85);
      motor_b.write(85);

    } else if (incomingByte == 57) {
      Serial.println(100);
      motor_a.write(100);
      motor_b.write(100);
    }
  }
}

