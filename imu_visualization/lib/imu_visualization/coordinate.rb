require 'ostruct'

class Coordinate < OpenStruct

  def initialize(x, y, z)
    super(:x => x, :y => y, :z => z)
  end

end
