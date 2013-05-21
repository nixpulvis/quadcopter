#include <Servo.h>
#include "motor.h"

/* Define some constants. */
#define NUM_MOTORS 4

/* Create the motors. */

Motor motor_a(6);  // Arduino pin 6.  (front-left prop)
Motor motor_b(9);  // Arduino pin 9.  (back-left prop)
Motor motor_c(10); // Arduino pin 10. (back-right prop)
Motor motor_d(11); // Arduino pin 11. (front-right prop)

// Store an array of pointers to the motors.
Motor* motors[NUM_MOTORS] = { &motor_a, &motor_b, &motor_c, &motor_d };

void setup() {
  Serial.begin(9600);

  /* Initialize the motors before anything else.
   * For the ESCs to operate the arduino must be attached and
   * sending 0% power when the ESCs gain power. Therefor the
   * ESCs must NOT have power during this part of the setup.
   */
  Serial.println("initializing");
  for (int i = 0; i < NUM_MOTORS; i++) {
    (*motors[i]).initialize();
  }

  // Now the ESCs may have power.
}

int incomingByte = 0; // for incoming serial data

void loop() {
  if (Serial.available() > 0) {
    incomingByte = Serial.read();

    if (incomingByte == 96) { // key: "`"
      Serial.println("attach");
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).attach();
      }

    } else if (incomingByte == 45) { // key: "-"
      Serial.println("detach");
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).detach();
      }

    } else if (incomingByte == 48) {
      Serial.println(0);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(0);
      }

    } else if (incomingByte == 49) {
      Serial.println(1);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(1);
      }

    } else if (incomingByte == 50) {
      Serial.println(13);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(13);
      }

    } else if (incomingByte == 51) {
      Serial.println(25);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(25);
      }

    } else if (incomingByte == 52) {
      Serial.println(37);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(37);
      }

    } else if (incomingByte == 53) {
      Serial.println(49);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(49);
      }

    } else if (incomingByte == 54) {
      Serial.println(61);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(61);
      }

    } else if (incomingByte == 55) {
      Serial.println(73);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(73);
      }

    } else if (incomingByte == 56) {
      Serial.println(85);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(85);
      }

    } else if (incomingByte == 57) {
      Serial.println(100);
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(100);
      }
    }
  }
}

