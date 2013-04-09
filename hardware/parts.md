# Quadrocopter Parts

WIP parts list for the 2013 quadrocopter. Everything here is subject to change until the parts are all bought.

## High Level Components

### Frame
[Turnigy Talon](http://www.hobbyking.com/hobbyking/store/__22397__Turnigy_Talon_Carbon_Fiber_Quadcopter_Frame.html) - $35

### Battery

Lots of power (less then 15v though), and lots of capacity. Maybe even 2 batteries?

__Measuring current capacity__  
In order to calculate current charge we may need to invest in a [ADC (Analog to digital converter)](http://en.wikipedia.org/wiki/Analog-to-digital_converter) and a small secondary reference battery.

### Motors / Propellers
[Turnigy Multistar](http://www.hobbyking.com/hobbyking/store/__26959__Turnigy_Multistar_4822_570Kv_22Pole_Multi_Rotor_Outrunner.html) - $30 (x4)

There are a million options but this one looks pretty nice. It's also worth noting that buying the motor and ESCs from the same company seems like a really smart idea.

### ESCs (Electronic Speed Controllers)

These should be pretty straightforward, we need ESCs that can handle the amount of current our battery will give out at most. Also the ESC should have an output to power the Flight control, and whatever else. This will be ~5v.

### Flight Control

We have some options here. There are pre-built controllers that will drive the ESCs and process the accelerometers, gyros, and barometers. This could be a good option however we lose the power of having our own arduino. We could then put another arduino on-board, but now the circuity is going to be getting cluttered.

### Radio Communication
[Xbee 802.15.4](https://www.sparkfun.com/products/8665) - $23 (x2)

We still need to work out how we intend to communincate with this project. From the computer, or a dedicated controller. Computer seems to make the most sense. In that case what are the requirments. Seems like we should be able to get away with any computer with a USB port and a [Xbee USB Adapter](https://www.sparkfun.com/products/8687)