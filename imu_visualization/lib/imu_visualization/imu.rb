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
    update_data  # Get a fresh set of data.

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
    @data = @serial_monitor.gets.split(" ").map { |e| e.to_i }
  end

  def update_position
    # TODO
  end

  def update_rotation
    vx, vy, vz = [@gyroscope.x, @gyroscope.y, @gyroscope.z].map { |e| e / 2000 }
    @rotation = Coordinate.new(
      @rotation.x + vx,
      @rotation.y + vy,
      @rotation.z + vz,
      vx,
      vy,
      vz
    )
  end
end
