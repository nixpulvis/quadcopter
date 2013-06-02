Stabilization
=============

Using sensor data from the accelerometer and gyroscope, stabilization can be
achieved in a number of ways. Here, I propose using a
[kalman filter](http://en.wikipedia.org/wiki/Kalman_filter) to combine the
accelerometer and gyro readings, and reduce the error produced by the sensors.

Problem
=======

It will be difficult to get consistently accurate and usable readings from the
gyroscope and accelerometer individually. [Gyroscopic drift is a real and
observable problem][1], but can be solved. it is also difficult to extract
meaningful data from pure accelerometer data. Accelerometer data is often noisy,
and it is almost impossible to dermine position data from a moving object using
only an accelerometer.

I suggest multiple solutions here:

 - Kalman Filter/Extended Kalman Filter
 - PID
 - Complementary Filter
 - DCM


Kalman Filter/Extended Kalman Filter
------------------------------------

Using a kalman filter to compute pitch and roll together will require relatively
heavy computation and would probably not be ideal for stabilizing a
quadrocopter.

Separating the pitch and roll estimates appears to be a more robust solution,
unless you are dealing with pitch/roll values that near the 90 degree mark.

State Model
-----------
The models for pitch and roll will be identical, and can be described using the
state `$x$`, where:

 - `$\Theta$` is the measured angle
 - `$\dot{\Theta}$` is the angular velocity
 - `$\dot{\Theta}_{b}$` is the bias in the angular velocity
 - why do these not render properly

 ```mathjax
  x =
 \begin{bmatrix}
 \Theta \\
 \dot{\Theta }\\
 \dot{\Theta}_{b}
 \end{bmatrix}
 ```

Prediction
----------

Using the model `$x$` defined above we can use the transformation

```mathjax
x_{k} = Fx_{(k-1)} + Bu_{k} + w_{k}
```
where:
 - `$F$` is the state transition model
 - `$x_{(k-1)}$` is the previous state
 - `$B$` is the control-input model
 - `$u_{k}$` is the control vector
 - `$w_{k}$` is the process noise.

 This is the skeleton of a Kalman Filter.

State Transition Model (`$F$`)
------------------------------

The state transition model, `$F$`, is used to compute the next state using the
previous state and the control signal.

We can use the following matrix for `$F$`:

```Mathjax
F =
\begin{bmatrix}
1 & \bigtriangleup t & -\bigtriangleup t \\
0 & 1                & 0
0 & 0                & 1
\end{bmatrix}
```


[1]:http://www.csulb.edu/~hill/ee400d/Reference%20Folder/Kalman%20Filter%20Research.pdf
