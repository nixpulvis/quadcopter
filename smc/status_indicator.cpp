#include <Arduino.h>
#include "status_indicator.h"

StatusIndicator::StatusIndicator(int red_pin, int green_pin) {
  _red_pin   = red_pin;
  _green_pin = green_pin;
  pinMode(_red_pin, OUTPUT);
  pinMode(_green_pin, OUTPUT);
}

void StatusIndicator::red(bool status) {
  digitalWrite(_red_pin, status ? HIGH : LOW);
  is_red = status;
}

void StatusIndicator::green(bool status) {
  digitalWrite(_green_pin, status ? HIGH : LOW);
  is_green = status;
}

void StatusIndicator::redOnly() {
  red(true);
  green(false);
}

void StatusIndicator::greenOnly() {
  green(true);
  red(false);
}

void StatusIndicator::toggleRed() {
  red(is_red ? false : true);
}

void StatusIndicator::toggleGreen() {
  green(is_green ? false : true);
}

