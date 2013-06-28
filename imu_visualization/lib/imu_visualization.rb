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
    # Make a copy of the identity matrix at the top of the stack.
    glPushMatrix

    # Move the corrdinate system based on IMU's position.
    glTranslatef(@imu.position.x, @imu.position.y, @imu.position.z)

    # Rotate to match IMU's current rotation.
    glRotatef(@imu.rotation.x, 1, 0, 0)
    glRotatef(@imu.rotation.y, 0, 1, 0)
    glRotatef(@imu.rotation.z, 0, 0, 1)

    # Draw the IMU.
    drawBox(0.35, 0.1, 0.45)

    # Remove the top of the stack of matrices, leaving the identity at the top.
    glPopMatrix
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
