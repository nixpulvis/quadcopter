#include <Arduino.h>
#include <Servo.h>
#include "motor.h"

#define MOTOR_ARM  8   // 8:   Send before power to arm.
#define MOTOR_LOW  62  // 62:  Off.
#define MOTOR_HIGH 113 // 113: Full Power.

Motor::Motor(int pin) {
  Servo _motor;
  _pin = pin;
}

// Initialize the ESC by attaching it and sending it low.
// This is well documented in the ESC manual.
// http://www.hobbyking.com/hobbyking/store/uploads/809043064X351363X29.pdf
//
void Motor::initialize() {
  attach();
  _motor.write(MOTOR_ARM);
}

// Using the Servo library, simply attach the servo object.
//
void Motor::attach() {
  _motor.attach(_pin);
}

// Using the Servo library, simply detach the servo object.
//
void Motor::detach() {
  _motor.detach();
}

// Power the motor to the given percent of it's max power. Rounding
// up to the nearest int value. This takes into account the MOTOR_LOW
// and MOTOR_HIGH values.
//
void Motor::write(int percent) {
  float val = ((MOTOR_HIGH - MOTOR_LOW) * (percent / 100.0)) + MOTOR_LOW;
  _motor.write(ceil(val));
}
