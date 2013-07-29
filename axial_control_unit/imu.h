#ifndef IMU_h
#define IMU_h

#include <Arduino.h>

#define ACCEL_FS MPU9150_ACCEL_FS_16
#define GYRO_FS  MPU9150_GYRO_FS_2000

class IMU
{
  public:
    VectorFloat axis_angle;

    void initialize();
    bool update();
    bool update(void (*post_update)());
    bool update(void (*pre_update)(), void (*post_update)());

  private:
    MPU9150 _mpu;
};

#endif
