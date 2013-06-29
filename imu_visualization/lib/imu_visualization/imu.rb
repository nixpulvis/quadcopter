require 'gel'
require 'imu_visualization/inertial_device'
require 'imu_visualization/coordinate'

class IMU < Gel::Box
  attr_reader :name, :position, :rotation

  def initialize(name, serialport, baud)
    super 0.5, 0.2, 0.7

    @name = name

    @serial_monitor = SerialMonitor.new(serialport, baud)
    update_data

    @accelerometer = InertialDevice.new(@data[0..2])
    @gyroscope     = InertialDevice.new(@data[3..5])
    @magnometer    = InertialDevice.new(@data[6..8])

    @position = Coordinate.new(0, 0, 0)
    @rotation = Coordinate.new(0, 0, 0)
  end

  # Update all the readings for the IMU's components.
  def update
    update_data           # Get a fresh set of data.
    update_time_interval  # Get the new time elapsed since last update.

    # Update all the inertial devices.
    @accelerometer.update(@data[0..2])
    @gyroscope.update(@data[3..5])
    @magnometer.update(@data[6..8])

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

  def update_time_interval
    running_time = glutGet(GLUT_ELAPSED_TIME)
    @time_interval = (running_time - (@running_time || 0)) / 1000.0
    @running_time  = running_time
  end

  def update_position
    # TODO
  end

  def update_rotation
    @rotation = Coordinate.new(
      @rotation.x + (@gyroscope.x * @time_interval),
      @rotation.y + (@gyroscope.y * @time_interval),
      @rotation.z + (@gyroscope.z * @time_interval),
      @gyroscope.x,
      @gyroscope.y,
      @gyroscope.z
    )
  end
end
