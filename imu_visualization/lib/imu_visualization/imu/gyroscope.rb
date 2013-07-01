class IMU::Gyroscope
  attr_accessor :delta_x, :delta_y, :delta_z

  def initialize(delta_x, delta_y, delta_z)
    update(delta_x, delta_y, delta_z)
  end

  def update(delta_x, delta_y, delta_z)
    elapsed_time  = glutGet(GLUT_ELAPSED_TIME)
    @delta_time   = (elapsed_time - (@elapsed_time || 0)) / 1000.0
    @elapsed_time = elapsed_time

    @last_x, @last_y, @last_z = @x || 0 , @y || 0, @z || 0
    @delta_x, @delta_y, @delta_z = delta_x, delta_y, delta_z

    @x = @last_x + (@delta_x * @delta_time)
    @y = @last_y + (@delta_y * @delta_time)
    @z = @last_z + (@delta_z * @delta_time)
  end

  def measurements
    [:pitch, :roll, :yaw]
  end

  def pitch
    @x
  end

  def roll
    @y
  end

  def yaw
    @z
  end
end
