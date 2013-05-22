#ifndef Motor_h
#define Motor_h

#include <Arduino.h>

class Motor
{
  public:
    Motor(int pin);
    void initialize();
    void attach();
    void detach();
    void write(int percent);

  private:
    Servo _motor;
    int   _pin;
};

#endif
