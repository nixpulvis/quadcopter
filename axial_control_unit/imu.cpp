#include <Arduino.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>
#include "imu.h"

// Raw MPU data.
int16_t raw_ax, raw_ay, raw_az, raw_gx, raw_gy, raw_gz;
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
  /* Read and scale the raw data from the MPU into proper units.
   * - Forces in (Gs) upon the x, y, z axes of the MPU.
   * - Angular velocity in degrees about the x, y, z axes.
   */
  _mpu.getMotion6(&raw_ax, &raw_ay, &raw_az, &raw_gx, &raw_gy, &raw_gz);
  accelerometer_force.x = raw_ax / a_scale;
  accelerometer_force.y = raw_ay / a_scale;
  accelerometer_force.z = raw_az / a_scale;
  gyroscope_velocity.x  = raw_gx / g_scale;
  gyroscope_velocity.y  = raw_gy / g_scale;
  gyroscope_velocity.z  = raw_gz / g_scale;

  /* Calculate the change in time from the last update to now. */
  float dt;
  if (last_time == 0) {
    dt = 0.0;
  } else {
    dt = (float)(micros() - last_time) / 1000000.0;
  }
  last_time = micros();

  /* Calculate the displacement in degrees of the current angle from the last
   * angle.
   */
  gyroscope_displacement.x = gyroscope_velocity.x * dt;
  gyroscope_displacement.y = gyroscope_velocity.y * dt;
  gyroscope_displacement.z = gyroscope_velocity.z * dt;

  // TODO
  // Quaternion gyro_quat = Quaternion(
  //   cos(gyroscope_displacement.x/2) * cos(gyroscope_displacement.y/2) * cos(gyroscope_displacement.z/2) + sin(gyroscope_displacement.x/2) * sin(gyroscope_displacement.y/2) * sin(gyroscope_displacement.z/2),
  //   cos(gyroscope_displacement.x/2) * sin(gyroscope_displacement.y/2) * cos(gyroscope_displacement.z/2) - sin(gyroscope_displacement.x/2) * cos(gyroscope_displacement.y/2) * sin(gyroscope_displacement.z/2),
  //   sin(gyroscope_displacement.x/2) * cos(gyroscope_displacement.y/2) * cos(gyroscope_displacement.z/2) + cos(gyroscope_displacement.x/2) * sin(gyroscope_displacement.y/2) * sin(gyroscope_displacement.z/2),
  //   cos(gyroscope_displacement.x/2) * cos(gyroscope_displacement.y/2) * sin(gyroscope_displacement.z/2) - sin(gyroscope_displacement.x/2) * sin(gyroscope_displacement.y/2) * cos(gyroscope_displacement.z/2)
  // );

  // quat = quat.getProduct(gyro_quat);
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
