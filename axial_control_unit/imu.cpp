#include <Arduino.h>
#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>
#include "imu.h"

// Raw MPU data.
int16_t raw_ax, raw_ay, raw_az, raw_gx, raw_gy, raw_gz;
float a_scale, g_scale;

// Kalman filter variables.
float Pxx = 0.1; // angle variance
float Pvv = 0.1; // angle change rate variance
float Pxv = 0.1; // angle / angle change rate covariance
float gyroVar = 0.1;
float deltaGyroVar = 0.1;
float accelVar = 5.0;

unsigned long last_time = 0;

void IMU::initialize() {
  Wire.begin();
  _mpu.initialize();

  /* Set the scale values for the raw data. */
  a_scale = 2048.0 * pow(2, 3 - _mpu.getFullScaleAccelRange());
  g_scale = 16.4 * pow(2, 3 - _mpu.getFullScaleGyroRange());

  /* Gyroscope spin-up time */
  delay(30);
}

int IMU::update() {
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

  float accelAngle[2];
  accelAngle[0] = atan2(accelerometer_force.z, accelerometer_force.y) * -360.0 / (2*PI) + 90.0;
  accelAngle[1] = atan2(accelerometer_force.z, accelerometer_force.x) * 360.0 / (2*PI) - 90.0;

  anglePrediction[0] += gyroscope_velocity.x * dt;
  anglePrediction[1] += gyroscope_velocity.y * dt;

  /* Kalman filter */
  Pxx += dt * (2 * Pxv + dt * Pvv);
  Pxv += dt * Pvv;
  Pxx += dt * gyroVar;
  Pvv += dt * deltaGyroVar;
  float kx = Pxx * (1.0 / (Pxx + accelVar));
  float kv = Pxv * (1.0 / (Pxx + accelVar));

  anglePrediction[0] += (accelAngle[0] - anglePrediction[0]) * kx;
  anglePrediction[1] += (accelAngle[1] - anglePrediction[1]) * kx;

  Pxx *= (1 - kx);
  Pxv *= (1 - kx);
  Pvv -= kv * Pxv;

  return dt;
}