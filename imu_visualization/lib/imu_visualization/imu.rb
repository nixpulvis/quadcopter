require 'imu_visualization/position'
require 'imu_visualization/rotation'

class IMU
  attr_accessor :position, :rotation
  attr_reader :name

  def initialize(name, position, rotation)
    @name = name
    @position = position
    @rotation = rotation
  end

  def reset(options = {})
    options = {:position => true, :rotation => true}.merge(options)

    if options[:position]
      position.x = 0
      position.y = 0
      position.z = 0
    end

    if options[:rotation]
      rotation.x = 0
      rotation.y = 0
      rotation.z = 0
    end
  end
end
