require 'imu_visualization/accelerable'

class Rotation
  include Accelerable
  attr_accessor :x, :y, :z

  def initialize(x, y, z)
    @x = x
    @y = y
    @z = z
    super(0, 0, 0)
  end
end
