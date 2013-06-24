# Quadrocopter

 * __Nathan Lilienthal__ [@nixpulvis](https://github.com/nixpulvis)
 * __Alex Johnson__ [@alexjohnson505](https://github.com/alexjohnson505)

## Index

This project is comprised of a number of components. Below is a purpose and description for each main peice.

### gel

Gel is a simple OpenGL engine, created to assist in understanding and analyzing data through 3D visualization. One such part is the 3D representation of data provided via the IMU.

### serial_monitor

Serial monitor reads data from the Arduino by wrapping the `SerialPort` class from the `serialport` gem.

The Arduino application's serial monitor is good for human reading the output, but Serial Monitor allows additional programs to read the data.

### imu_visualization

IMU_visualization reads IMU data from the Arduino over serial, and creates 3D models of the data allowing us to create a visual 3D represenation of the captured data.

### smc

This program will sit on an Arduino acting as the quadcopter's SMC. It handles reading IMU data over I2C and performing the required math to accurately determinate valid pitch, roll, and yaw values. Based on it's knowledge of the quadcopters current inertial status, the SMC will drive the motors to the correct speed required to reach the calculated pitch, roll, yaw values.

## Tasks

We are maintaining the action items for this project on [Trello](https://trello.com/b/EygHwZfX).