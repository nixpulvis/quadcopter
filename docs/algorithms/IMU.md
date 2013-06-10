# IMU #

Some notes on IMU calculations:

where `N` is the a-d reading:

Measured acceleration to SI units:
    (A) acceleration (m/s^2) = (N-512)/1024*(double)10.78;
should replace 512 with the measured zero-g bias.

Measured yaw rate to SI units:
    rate = (N-512)/1024 * (double) 28.783;
again, replace 512 with the measured zero-g bias.
