#include <Servo.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>

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

bool running = false;
void loop() {
  imu.update(&postUpdate);

  if (Serial.available() > 0) {
    if (Serial.read() == 49) {
      running = true;
      motor_b.write(20);
      motor_c.write(20);
    } else {
      running = false;
      for (int i = 0; i < NUM_MOTORS; i++) {
        (*motors[i]).write(0);
      }
    }
  }

  if (running) {
    int delta = imu.quaternion.y/.071;

    if (delta >= 10) delta = 10;
    else if (delta <= -10) delta = -10;

    motor_b.write(20+delta);
    motor_c.write(20-delta);
  }
}

void postUpdate() {
  activity();
  // printQuaternion();
}

void printQuaternion() {
  Serial.print(imu.quaternion.w);
  Serial.print("\t");
  Serial.print(imu.quaternion.x);
  Serial.print("\t");
  Serial.print(imu.quaternion.y);
  Serial.print("\t");
  Serial.println(imu.quaternion.z);
}

void activity() {
  status.toggleGreen();
}
