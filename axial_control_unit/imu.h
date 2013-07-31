#ifndef IMU_h
#define IMU_h

#include <Arduino.h>

class IMU
{
  public:
    VectorFloat accelerometer_force;
    VectorFloat gyroscope_velocity;
    VectorFloat gyroscope_displacement;
    Quaternion quat;

    void initialize();
    bool update();
    bool update(void (*post_update)());
    bool update(void (*pre_update)(), void (*post_update)());

  private:
    MPU9150 _mpu;
};

#endif
