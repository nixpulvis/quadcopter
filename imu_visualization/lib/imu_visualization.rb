require 'serial_monitor'
require 'gel'
require 'imu_visualization/imu'

class IMUVisualization < Gel

  def setup
    @imu = IMU.new("MPU-9150", ARGV[0], 38400)
  end

  def loop
    @imu.update
  end

  def draw
    @imu.draw
  end

  def keyboard(key, x, y)
    case key
    when 'c'
      @imu.calibrate
    when ' '
      puts <<-EOS
IMU (#{@imu.name})
  Position : X = #{@imu.position.x}, Y = #{@imu.position.y}, Z = #{@imu.position.z}
  Rotation : X = #{@imu.rotation.x}, Y = #{@imu.rotation.y}, Z = #{@imu.rotation.z}"
EOS
    when "\e"
      exit(0)
    end
  end

end
