# Quadrocopter

 * __Nathan Lilienthal__ [@nixpulvis](https://github.com/nixpulvis)
 * __Alex Johnson__ [@alexjohnson505](https://github.com/alexjohnson505)

## Index

This project is made up of a number of components, below are the names of each component and a description of what it does.

### gel

This is a super simple OpenGL engine, created to assist with other parts of the project needing visualization of 3D objects (IMU data).

### serial_monitor

When developing for the Arduino it is almost always helpful to send information over serial to debug issues and to communicate data. The Arduino application's serial monitor is good for human reading the output, but we want to be able to use the data. Serial monitor allows us to read the data from the Arduino reliably, by wrapping the `SerialPort` class from the `serialport` gem.

### imu_visualization

To understand better what data we are working with from the IMU itself, this component of the project reads IMU data from the Arduino over serial, and creates 3D models of the data.

### smc

This component is the code that will sit on an Arduino acting as the quadcopter's SMC. It handles reading IMU data over I2C and performing the required math to accurately determinate valid pitch, roll, and yaw values. More information will be collected as well. Then based on it's knowledge of the quadcopters current inertial status, the SMC will drive the motors to the correct speed to reach the given pitch, roll, yaw values.

## Tasks

We are maintaining the action items for this project on [Trello](https://trello.com/b/EygHwZfX).
