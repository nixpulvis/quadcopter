#include <Arduino.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>
#include "imu.h"

// Raw MPU data.
int16_t raw_ax, raw_ay, raw_az, raw_gx, raw_gy, raw_gz;
float ax, ay, az, gx, gy, gz;
float a_scale, g_scale;

unsigned long last_time = 0;

void IMU::initialize() {
  Wire.begin();

  _mpu.initialize();
  _mpu.setFullScaleAccelRange(ACCEL_FS);
  a_scale = 2048.0 * pow(2, 3 - ACCEL_FS);
  _mpu.setFullScaleGyroRange(GYRO_FS);
  g_scale = 16.4 * pow(2, 3 - GYRO_FS);
}

bool IMU::update() {
  _mpu.getMotion6(&raw_ax, &raw_ay, &raw_az, &raw_gx, &raw_gy, &raw_gz);
  ax = raw_ax / a_scale;
  ay = raw_ay / a_scale;
  az = raw_az / a_scale;
  gx = raw_gx / a_scale;
  gy = raw_gy / a_scale;
  gz = raw_gz / a_scale;

  float dt;
  if (last_time == 0) {
    dt = 0.0;
  } else {
    dt = (float)(micros() - last_time) / 1000000.0;
  }
  last_time = micros();

}

bool IMU::update(void (*post_update)()) {
  if (update()) {
    post_update();
    return true;
  }
  return false;
}

bool IMU::update(void (*pre_update)(), void (*post_update)()) {
  pre_update();

  if (update()) {
    post_update();
    return true;
  }
  return false;
}
