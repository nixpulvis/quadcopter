#ifndef STATUS_INDICATOR_h
#define STATUS_INDICATOR_h

#include <Arduino.h>

class StatusIndicator
{
  public:
    bool is_red;
    bool is_green;

    StatusIndicator(int red_pin, int green_pin);

    void red(bool status);
    void green(bool status);
    void redOnly();
    void greenOnly();
    void toggleRed();
    void toggleGreen();

  private:
    int _red_pin;
    int _green_pin;
};

#endif
