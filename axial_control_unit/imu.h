#ifndef IMU_h
#define IMU_h

#include <Arduino.h>

class IMU
{
  public:
    VectorFloat accelerometer_force;
    VectorFloat gyroscope_velocity;
    VectorFloat gyroscope_displacement;
    float anglePrediction[2];

    void initialize();
    int update();

  private:
    MPU9150 _mpu;
};

#endif
