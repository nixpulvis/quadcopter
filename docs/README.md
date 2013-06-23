# Quadrocopter Documentation

Discoveries and details will be explained and referenced here. Hardware mentioned should reflect the current build.

For reference here are a collection of [useful links](links.md).

More information available on [Trello](https://trello.com/b/EygHwZfX).

## Overview

Below is an introduction into the quadcopter's overall design.

For more specific inner workings, refer to individual [components](#components).

### Control
Here is a high level view of the project's design.

Using two distinct units for controlling the quadrocopter (Raspberry Pi, and Arduino mini) allows for a far more dynamic interface to control it with. While the Arduino mini is capable of handling many of the low-level tasks such as motor control, and data collection, the Raspberry Pi can run logic and more advanced programs running in Ruby, or other high level languages.

![](images/control.jpg)

### Power
Powering the quadrocopter is 1 3000 mAh LiPo battery. It's a 4 cell battery @ 14.8 V. The following diagram shows how the system is powered.

![](images/power.jpg)

## Components

Here lies the details of the individual components of the system.

### Ours
 - [SMC (Stable Motor Controller)](components/smc.md)
 - [FCU (Flight Control Unit)](components/fcu.md)

### Vendor
 - [ESCs](components/esc.md)
 - [Battery](components/battery.md)
