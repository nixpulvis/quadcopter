require 'gel'

class MovingBoxExample < Gel

  # Runs once before the main loop.
  def setup
    super # Do the default setup.

    # Make a multi colored box.
    @box = Gel::Box.new 0.25, 0.25, 0.25, {
      :front  => [1, 0, 0],
      :back   => [1, 1, 0],
      :left   => [1, 1, 1],
      :right  => [0, 1, 1],
      :top    => [0, 1, 0],
      :bottom => [0, 0, 1],
    }

    # Save the state of a rotation.
    @rotation = { :x => 0, :y => 0, :z => 0 }
  end

  # Runs while idle.
  def loop
    @rotation.each { |k,v| @rotation[k] += 0.01 }
  end

  # Runs when OpenGL asks for rendering.
  def draw
    # Make a copy of the identity matrix at the top of the stack.
    glPushMatrix

    # Rotate to match IMU's current rotation.
    glRotatef(@rotation[:x], 1, 0, 0)
    glRotatef(@rotation[:y], 0, 1, 0)
    glRotatef(@rotation[:z], 0, 0, 1)

    # Draw the IMU.
    @box.draw

    # Remove the top of the stack of matrices, leaving the identity at the top.
    glPopMatrix
  end

end

MovingBoxExample.new("Box Example", 500, 500)
