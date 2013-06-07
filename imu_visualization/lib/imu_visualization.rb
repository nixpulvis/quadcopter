require 'gel'
require 'imu_visualization/imu'

class IMUVisualization < Gel
  attr_reader :imu

  def setup
    initial_position = Position.new(0, 0, 0)
    initial_rotation = Rotation.new(0, 0, 0)
    @imu = IMU.new("MPU-9150", initial_position, initial_rotation)
  end

  def loop
    if @auto
      @imu.rotation.x = (@imu.rotation.x + 0.1) % 360
      @imu.rotation.y = (@imu.rotation.y + 0.1) % 360
      @imu.rotation.z = (@imu.rotation.z + 0.1) % 360
    end
  end

  def draw
    glTranslatef(@imu.position.x, @imu.position.y, @imu.position.z)

    # Rotate to match `rotate_x` and `rotate_y`.
    glRotatef(@imu.rotation.x, 1, 0, 0)
    glRotatef(@imu.rotation.y, 0, 1, 0)
    glRotatef(@imu.rotation.z, 0, 0, 1)

    # Draw a box.
    drawBox(0.35, 0.1, 0.45)
  end

  def keyboard(key, x, y)
    case key
    when 'd'
      @imu.rotation.y = (@imu.rotation.y + 5) % 360
    when 'a'
      @imu.rotation.y = (@imu.rotation.y - 5) % 360
    when 'w'
      @imu.rotation.x = (@imu.rotation.x + 5) % 360
    when 's'
      @imu.rotation.x = (@imu.rotation.x - 5) % 360
    when 'r'
      @imu.rotation.z = (@imu.rotation.z + 5) % 360
    when 'l'
      @imu.rotation.z = (@imu.rotation.z - 5) % 360
    when 'f'
      @imu.position.z += 0.05
    when 'b'
      @imu.position.z -= 0.05
    when 'q'
      @auto = !@auto
    when 'e'
      @imu.reset
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

  def special_keyboard(key, x, y)
    case key
    when GLUT_KEY_LEFT
      @imu.position.x -= 0.05
    when GLUT_KEY_RIGHT
      @imu.position.x += 0.05
    when GLUT_KEY_UP
      @imu.position.y += 0.05
    when GLUT_KEY_DOWN
      @imu.position.y -= 0.05
    end
  end

end
