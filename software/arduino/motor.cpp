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

void Motor::initialize() {
  attach();
  write(0);
  Serial.println("initialized");
}

void Motor::attach() {
  _motor.attach(_pin);
}

void Motor::detach() {
  _motor.detach();
}

void Motor::write(int percent) {
  float val = ((MOTOR_HIGH - MOTOR_LOW) * (percent / 100.0)) + MOTOR_LOW;
  _motor.write(ceil(val));
}
