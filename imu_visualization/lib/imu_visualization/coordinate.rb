class Coordinate
  attr_reader :x, :y, :z

  def initialize(x, y, z)
    @x, @y, @z = x, y, z
  end

  def [](key)
    send(key)
  end

end
