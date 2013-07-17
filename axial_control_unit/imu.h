#ifndef IMU_h
#define IMU_h

#include <Arduino.h>

class IMU
{
  public:
    Quaternion quaternion;

    void initialize();
    bool update();
    bool update(void (*post_update)());
    bool update(void (*pre_update)(), void (*post_update)());

  private:
    MPU9150       _mpu;
    uint16_t      _packetSize;
    uint16_t      _fifoCount;
    uint8_t       _fifoBuffer[64];

    static volatile bool _int;
    static void _interruptServiceRoutine();
};

#endif
