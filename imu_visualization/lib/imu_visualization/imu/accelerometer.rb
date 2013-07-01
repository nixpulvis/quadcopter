class IMU::Accelerometer
  attr_reader :force_magnitude

  def initialize(x, y, z)
    update(x, y, z)
  end

  def update(x, y, z)
    @x, @y, @z = x, y, z
    @force_magnitude = Math.sqrt(@x**2 + @y**2 + @z**2)
  end

  def pitch
    (Math.atan2(@y, @z)) * 180/Math::PI
  end

  def roll
    (Math.atan2(@x, @z)) * 180/Math::PI
  end
end
