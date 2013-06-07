require 'gel'

class IMUVisualization < Gel
  attr_reader :rotate_x, :rotate_y, :rotate_z

  def setup
    # 3D rotation in degrees.
    @rotate_x = 0
    @rotate_y = 0
    @rotate_z = 0
  end

  def draw
    # Rotate to match `rotate_x` and `rotate_y`.
    glRotatef(@rotate_x, 1.0, 0.0, 0.0)
    glRotatef(@rotate_y, 0.0, 1.0, 0.0)
    glRotatef(@rotate_z, 0.0, 0.0, 1.0)

    # Draw a box.
    drawBox(0.5, 0.15, 0.65)
  end

  def keyboard(key, x, y)
    if key == 'd'
      @rotate_y = (@rotate_y + 5) % 360
    elsif key == 'a'
      @rotate_y = (@rotate_y - 5) % 360
    elsif key == 'w'
      @rotate_x = (@rotate_x + 5) % 360
    elsif key == 's'
      @rotate_x = (@rotate_x - 5) % 360
    elsif key == 'r'
      @rotate_z = (@rotate_z + 5) % 360
    elsif key == 'l'
      @rotate_z = (@rotate_z - 5) % 360
    elsif key == ' '
      puts self
    elsif key == "\e"
      exit(0)
    end
  end

  def to_s
    "X: #{rotate_x}, Y: #{rotate_y}, Z: #{rotate_z}"
  end

end
