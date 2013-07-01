class IMU::Magnometer
  attr_reader :x, :y, :z

  def initialize(x, y, z)
    update(x, y, z)
  end

  def update(x, y, z)
    @x, @y, @z = x, y, z
  end
end
