require 'gel'
require 'imu_visualization/accelerometer'
require 'imu_visualization/gyroscope'
require 'imu_visualization/magnometer'
require 'imu_visualization/coordinate'

class IMU < Gel::Box
  attr_reader :name, :position, :rotation

  def initialize(name, serialport, baud)
    super 0.5, 0.2, 0.7

    @name = name

    @serial_monitor = SerialMonitor.new(serialport, baud)
    update_data

    @accelerometer = Accelerometer.new *@data[0..2]
    @gyroscope     = Gyroscope.new     *@data[3..5]
    @magnometer    = Magnometer.new    *@data[6..8]

    @position = Coordinate.new(0, 0, 0)
    @rotation = Coordinate.new(0, 0, 0)
  end

  # Update all the readings for the IMU's components.
  def update
    update_data           # Get a fresh set of data.

    # Update all the inertial devices.
    @accelerometer.update *@data[0..2]
    @gyroscope.update     *@data[3..5]
    @magnometer.update    *@data[6..8]

    # Calculate new positions and rotations.
    update_position
    update_rotation
  end

  def calibrate
    warn "Not implemented yet."
  end

  private

  # Get a new set of IMU data over serial.
  def update_data
    @data = @serial_monitor.gets.split("\t").map { |e| e.to_f }
  end

  def update_position
    # TODO
  end

  def update_rotation
    estimates = [
      [:x, @gyroscope.x, @accelerometer.pitch],
      [:y, @gyroscope.y, @accelerometer.roll],
      [:z, @gyroscope.z],
    ].map do |axis, *readings|
      estimate_angle(axis, readings, @time_interval)
    end

    @rotation = Coordinate.new(*estimates)
  end

  private

  # @angle is the previously estimated angle using both gyro and accel data
  def estimate_angle(axis, readings, dt)
    if axis == :z
      readings[0]
    else
      0.98 * readings[0] + (0.02 * readings[1])
    end
  end
end
