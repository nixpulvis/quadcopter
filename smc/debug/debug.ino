#include "Wire.h"
#include "I2Cdev.h"
#include "MPU6050.h"

MPU6050 imu;

// Status LEDs.
#define GREEN_LED 7
#define RED_LED 8

// Set the full scale range for the components of the IMU.
#define ACCEL_FULL_SCALE_RANGE MPU6050_ACCEL_FS_8
#define GYRO_FULL_SCALE_RANGE  MPU6050_GYRO_FS_500

float ACCEL_SCALE;
float GYRO_SCALE;

void setup() {
  // Setup status LEDs.
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);

  // Indicate we're getting setup.
  statusLight(0);

  // join I2C bus (I2Cdev library doesn't do this automatically)
  Wire.begin();

  // initialize serial communication
  // (38400 chosen because it works as well at 8MHz as it does at 16MHz)
  Serial.begin(38400);

  // initialize device
  imu.initialize();

  /* set accelerometer range.
   * MPU6050_ACCEL_FS_2(0)  : 2 g max  : Scale 16384
   * MPU6050_ACCEL_FS_4(1)  : 4 g max  : Scale 8192
   * MPU6050_ACCEL_FS_8(2) : 8 g max   : Scale 4096
   * MPU6050_ACCEL_FS_16(3) : 16 g max : Scale 2048
   */
  imu.setFullScaleAccelRange(ACCEL_FULL_SCALE_RANGE);
  ACCEL_SCALE = 16384 / pow(2, ACCEL_FULL_SCALE_RANGE);

  /* set gyro range.
   * MPU6050_GYRO_FS_250(0)  : 250 deg/sec max  : Scale 131.0
   * MPU6050_GYRO_FS_500(1)  : 500 deg/sec max  : Scale 65.5
   * MPU6050_GYRO_FS_1000(2) : 1000 deg/sec max : Scale 32.8
   * MPU6050_GYRO_FS_2000(3) : 2000 deg/sec max : Scale 16.4
   */
  imu.setFullScaleGyroRange(GYRO_FULL_SCALE_RANGE);
  GYRO_SCALE = 131 / pow(2, GYRO_FULL_SCALE_RANGE);
}

void loop() {
  // Indicate we're up and running.
  statusLight(1);

  int16_t ax, ay, az;  // g forces
  int16_t gx, gy, gz;  // degrees/second
  int16_t mx, my, mz;  // TODO: learn wtf data this is.

  // read raw accel/gyro measurements from device
  imu.getMotion9(&ax, &ay, &az, &gx, &gy, &gz, &mx, &my, &mz);

  // write accelerometer values (g)
  Serial.print(scale(ax, ACCEL_SCALE));
  Serial.print("\t");
  Serial.print(scale(ay, ACCEL_SCALE));
  Serial.print("\t");
  Serial.print(scale(az, ACCEL_SCALE));
  Serial.print("\t");

  // write gyroscope values (degrees/second)
  Serial.print(scale(gx, GYRO_SCALE));
  Serial.print("\t");
  Serial.print(scale(gy, GYRO_SCALE));
  Serial.print("\t");
  Serial.print(scale(gz, GYRO_SCALE));
  Serial.print("\t");

  // TODO: complete this.
  // write raw magnetometer values (??)
  Serial.print(mx);
  Serial.print("\t");
  Serial.print(my);
  Serial.print("\t");
  Serial.print(mz);

  Serial.println("");
}

float scale(int16_t value, float scale_factor) {
  return value / scale_factor;
}

void statusLight(bool state) {
  digitalWrite(GREEN_LED, state ? HIGH : LOW);
  digitalWrite(RED_LED, state ? LOW : HIGH);
}
