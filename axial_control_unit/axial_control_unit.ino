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

/* We want to be level "for now" */
float desired_angle[2]  = {0.0, 0.0};
float error_integral[2] = {0.0, 0.0};

enum State {
  SETUP   = 0,
  RUNNING = 1,
  OFF     = 2,
  RUNNING2 = 3,
};

State state = SETUP;

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
}

void loop() {
  switch(state) {
    case RUNNING:
      running(25); break;
    case OFF:
      off(); break;
    case RUNNING2:
      running(30); break;
  }
}

void serialEvent() {
  if (Serial.read() == '1') {
    state = RUNNING;
  } else if (Serial.read() == '2') {
    state = RUNNING2;
  } else {
    state = OFF;
  }
}

void running(int power) {
  status.red(false);

  int dt = imu.update();
  status.toggleGreen();

  /* PID controller
   */
  float error[2];
  error[0] = imu.anglePrediction[0] - desired_angle[0];
  error[1] = imu.anglePrediction[1] - desired_angle[1];

  float proportional[2], integral[2], derivative[2];
  int output[2];

  #define GAIN_PROPORTIONAL 0.17
  proportional[0] = error[0] * GAIN_PROPORTIONAL;
  proportional[1] = error[1] * GAIN_PROPORTIONAL;

  error_integral[0] += error[0] * dt;
  error_integral[1] += error[1] * dt;
  #define GAIN_INTEGRAL 0.015
  integral[0] = error_integral[0] * GAIN_INTEGRAL;
  integral[1] = error_integral[1] * GAIN_INTEGRAL;

  #define GAIN_DERIVATIVE 0.022
  derivative[0] = imu.gyroscope_velocity.x * GAIN_DERIVATIVE;
  derivative[1] = imu.gyroscope_velocity.y * GAIN_DERIVATIVE;

  output[0] = proportional[0] + integral[0] + derivative[0];
  output[1] = proportional[1] + integral[1] + derivative[1];

  if (output[0] > 5) {
    output[0] = 5;
  }
  if (output[1] > 5) {
    output[1] = 5;
  }

  (*motors[2]).write(power + output[0]);
  (*motors[3]).write(power - output[0]);

  (*motors[0]).write(power + output[1]);
  (*motors[1]).write(power - output[1]);
}

void off() {
  status.redOnly();

  /* Kill all the motors */
  for (int i = 0; i < NUM_MOTORS; i++) {
    (*motors[i]).write(0);
  }
}
