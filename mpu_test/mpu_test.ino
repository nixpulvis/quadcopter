#include <Wire.h>
#include <I2Cdev.h>
#include <MPU9150.h>

float a_scale, g_scale;

typedef struct {
  int16_t ax, ay, az;
  int16_t gx, gy, gz;
} MPU_Raw;

MPU9150 mpu;
MPU_Raw raw;

void setup() {
  Serial.begin(38400);
  Wire.begin();

  mpu.initialize();

  /* Set the scale values for the raw data. */
  a_scale = 2048.0 * pow(2, 3 - mpu.getFullScaleAccelRange());
  g_scale = 16.4 * pow(2, 3 - mpu.getFullScaleGyroRange());

  /* Gyroscope spin-up time */
  delay(30);

}

void loop() {
  /* Read and scale the raw data from the MPU into proper units.
   * - Forces in (Gs) upon the x, y, z axes of the MPU.
   * - Angular velocity in degrees about the x, y, z axes.
   */
  int16_t raw_ax, raw_ay, raw_az;
  mpu.getMotion6(&raw_ax, &raw_ay, &raw_az, &raw.gx, &raw.gy, &raw.gz);
  /* raw_ax = raw_ax / a_scale; */
  /* raw_ay = raw_ay / a_scale; */
  /* raw_az = raw_az / a_scale; */
  /* raw.gx  = raw.gx / g_scale; */
  /* raw.gy  = raw.gy / g_scale; */
  /* raw.gz  = raw.gz / g_scale; */

  Serial.print(raw_ax  / a_scale);
  Serial.print(", ");
  Serial.print(raw_ay / a_scale);
  Serial.print(", ");
  Serial.println(raw_az / a_scale);
}

void serialEvent() {
}
