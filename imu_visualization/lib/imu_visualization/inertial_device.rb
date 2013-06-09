class InertialDevice
  attr_reader :x, :y, :z

  def initialize(data)
    update(data)
  end

  def update(data)
    @x, @y, @z = data
  end
end
