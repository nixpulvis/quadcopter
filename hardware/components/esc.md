# ESCs

> ESC - Electronic Speed Controller.

See [this trello card](https://trello.com/c/xdSZhzF7) for the link to the ESC's product page.

### Motor connection

The motor can be attached to the ESC by simply connecting the 3 output wires of the ESC to the 3 wires of the motor. There is not a required color matching or anything like that.

If the motor is rotating the incorrect __direction__, simply swap two wires and it will spin the other direction.

### Power

The ESCs have a red wire and a black wire to power itself, the motor and pass 5v (needs verification) to the 3 pin controller connection.

__Current__: The documentation online states the power allowed by the ESC is 25A or 35A burst.  
__Voltage__: The documentation online states the voltage must be within 2-4C. C being LiPo Cells @ 3.7 V each. Making the minimum voltage 7.4V and the maximum voltage 14.8V

### Arming and controlling

After much trial and error, and then a little reading of included documentation, We've learned how to operate these buggers.

##### Connections

The ESC has a 3 pin motor wire. The white wire is data, black is ground and red is 5v (needs verification). It's important to note that the red wire should never be connected to a arduino `Vout` (`5v` or `3.3v`) pin. This wire will be used to actually power the board via `Vin`.

The white wire must pass a PWM signal to the ESC to control the motor's speed. The PWM signal is most easily controlled with the arduino's Servo library. The value passed to `write()` normally degrees between 0 and 180, are now the speed values. However some calibration is needed.

Calibration done via code accounts for the highest value for `write()` before the motor starts turning, and the lowest value for `write()` where increasing the value makes no effect on the RPM of the motor.

You can see how I'm handling calibration in `motor.cpp`.

``` c++
#define MOTOR_LOW  62  // 62:  Off.
#define MOTOR_HIGH 113 // 113: Full Power.

//...

// Power the motor to the given percent of it's max power. Rounding
// up to the nearest int value. This takes into account the MOTOR_LOW
// and MOTOR_HIGH values.
//
void Motor::write(int percent) {
  float val = ((MOTOR_HIGH - MOTOR_LOW) * (percent / 100.0)) + MOTOR_LOW;
  _motor.write(ceil(val));
}
```

##### Before power

Before the ESCs are given power the data wire must be given a specific signal to indicate it's intended to be armed. If the ESC is not given this signal when it gains power it will not function.

Again, after trial and error, the signal required by the ESC to arm was found to be 8-10 via `write()`.

Here is the relevant section of `motor.cpp`.

``` c++
#define MOTOR_ARM  8   // 8:   Send before power to arm.

//...

// Initialize the ESC by attaching it and sending it low.
// This is well documented in the ESC manual.
// http://www.hobbyking.com/hobbyking/store/uploads/809043064X351363X29.pdf
//
void Motor::initialize() {
  attach();
  _motor.write(MOTOR_ARM);
}
```
After this function the ESC can be powered and will be ready to operate.

##### Operation

It's very easy at this point. Using `motor.cpp`.

 - `write(int)` - Tell the motor to run at the given speed (percent 0-100).
 - `attach` - Can be thought of as physically connecting the data wire.
 - `detach` - Can be thought of as physically disconnecting the data wire. It can take a moment for the ESC to recognize this and kill power. When reattached it will be writing whatever value it was at when disconnected.

