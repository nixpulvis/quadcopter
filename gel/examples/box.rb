require 'bundler/setup'
require 'gel'

class RandomBox < Gel::Box

  def initialize(color)
    super 0.25, 0.75, 0.5, {
      :front  => color.map { |e| e += 0.1 },
      :back   => color.map { |e| e += 0.1 },
      :left   => color,
      :right  => color,
      :top    => color.map { |e| e -= 0.1 },
      :bottom => color.map { |e| e -= 0.1 },
    }
  end

  def update_rotation
    self.rotation = {
      :x => rand * 360,
      :y => rand * 360,
      :z => rand * 360,
    }
  end
end

class RandomBoxExample < Gel

  def setup
    @box = RandomBox.new [0.45, 0.35, 0.25]
  end

  def loop
    @box.update_rotation and sleep 0.5
  end

  def draw
    @box.draw
  end

end

RandomBoxExample.new("Random Box Example", 500, 500)
