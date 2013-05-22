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

void loop() {
  if (Serial.available() > 0) {
    int percent = Serial.parseInt();

    for (int i = 0; i < NUM_MOTORS; i++) {
      Serial.println(percent);
      (*motors[i]).write(percent);
    }
  }
}

