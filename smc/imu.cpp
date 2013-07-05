#include <Arduino.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>
#include "imu.h"

// Initialize the _int to be false (At the beginning there were no interrupts.)
// *note the IMU class can only handle 1 mpu since we have a static interupt
// state variable.
volatile bool IMU::_int = false;

void IMU::initialize() {
  Wire.begin();

  _mpu.initialize();
  _mpu.dmpInitialize();
  _mpu.setDMPEnabled(true);
  attachInterrupt(0, _interruptServiceRoutine, RISING);
  _packetSize = _mpu.dmpGetFIFOPacketSize();
}

bool IMU::update() {
  if (_int == true && _mpu.getIntStatus() & 0x02) {
    _int = false;

    while (_fifoCount < _packetSize) _fifoCount = _mpu.getFIFOCount();
    _mpu.getFIFOBytes(_fifoBuffer, _packetSize);
    _fifoCount -= _packetSize;

    _mpu.dmpGetQuaternion(&quaternion, _fifoBuffer);
    return true;
  }
  return false;
}

bool IMU::update(void (*post_update)()) {
  if (update()) {
    post_update();
    return true;
  }
  return false;
}

bool IMU::update(void (*pre_update)(), void (*post_update)()) {
  if (_int == true) {
    pre_update();

    if (update()) {
      post_update();
      return true;
    }
  }
  return false;
}

void IMU::_interruptServiceRoutine() {
  _int = true;
}
