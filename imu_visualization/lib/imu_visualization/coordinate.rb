class Coordinate
  attr_reader :x, :y, :z, :vx, :vy, :vz

  def initialize(x, y, z, vx = 0, vy = 0, vz = 0)
    @x, @y, @z, @vx, @vy, @vz = x, y, z, vx, vy, vz
  end

  def [](key)
    send(key)
  end

end
