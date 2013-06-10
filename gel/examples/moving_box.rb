require 'gel'

class MovingBoxExample < Gel

  # Runs once before the main loop.
  def setup
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
    drawBox(0.35, 0.1, 0.45)

    # Remove the top of the stack of matrices, leaving the identity at the top.
    glPopMatrix
  end

end

MovingBoxExample.new("Box Example", 500, 500)
