require 'imu_visualization/position'
require 'imu_visualization/rotation'

class IMU
  attr_accessor :position, :rotation
  attr_reader :name

  def initialize(name, position, rotation)
    @name = name
    @position = position
    @rotation = rotation

    @accelerometer = Accelerometer.new
    @gyroscope = Gyroscope.new
    @magnometer = Magnometer.new

    @serial_monitor = SerialMonitor.new('/dev/tty.usbmodem411', 38400, "\n")
  end

  def update(data = {})
    ax, ay, az,
    gx, gy, gz,
    mx, my, mz = @serial_monitor.gets.split(" ").map { |e| e.to_i }

    @accelerometer.update(ax, ay, az)
    @gyroscope.update(gx, gy, gz)
    @magnometer.update(mx, my, mz)

  end

  def reset(options = {})
    options = {:position => true, :rotation => true}.merge(options)

    if options[:position]
      position.x = 0
      position.y = 0
      position.z = 0
    end

    if options[:rotation]
      rotation.x = 0
      rotation.y = 0
      rotation.z = 0
    end
  end
end
