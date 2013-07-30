#include <Servo.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>
#include <MatrixMath.h>

#include "motor.h"
#include "status_indicator.h"
#include "imu.h"

/* Define some constants. */
#define NUM_MOTORS 4

/* Create the motors. */
Motor motor_a(6);  // Arduino pin 6.  (front-left prop)
Motor motor_b(9);  // Arduino pin 9.  (back-left prop)
Motor motor_c(10); // Arduino pin 10. (back-right prop)
Motor motor_d(11); // Arduino pin 11. (front-right prop)

// Store an array of pointers to the motors.
Motor* motors[NUM_MOTORS] = { &motor_a, &motor_b, &motor_c, &motor_d };

/* Create the status indicator. */
StatusIndicator status(8, 7);

/* Create an IMU. */
IMU imu;


void setup() {
  status.redOnly();

  Serial.begin(38400);

  imu.initialize();

  /* Initialize the motors before anything else.
   * For the ESCs to operate the arduino must be attached and
   * sending 0% power when the ESCs gain power. Therefor the
   * ESCs must NOT have power during this part of the setup.
   */
  for (int i = 0; i < NUM_MOTORS; i++) {
    (*motors[i]).initialize();
  }

  // Now the ESCs may have power.
  status.greenOnly();
}

void loop() {
  imu.update(&postUpdate);
  Serial.print("x ");
  Serial.print(imu.gyroscope_displacement.x);
  Serial.print("\ty ");
  Serial.print(imu.gyroscope_displacement.y);
  Serial.print("\tz ");
  Serial.println(imu.gyroscope_displacement.z);
}

void postUpdate() {
  status.toggleGreen();
}
