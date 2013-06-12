require 'gel'

class FixedBoxExample < Gel

  # Runs once before the main loop.
  def setup
    super # Do the default setup.

    # Make a multi colored box.
    @box = Gel::Box.new 0.50, 0.25, 0.25, {
      :front  => [1, 0, 0],
      :back   => [1, 1, 0],
      :left   => [1, 1, 1],
      :right  => [0, 1, 1],
      :top    => [0, 1, 0],
      :bottom => [0, 0, 1],
    }
  end

  # Runs when OpenGL asks for rendering.
  def draw
    # Make a copy of the identity matrix at the top of the stack.
    glPushMatrix

    # Move the corrdinate system based on IMU's position.
    glTranslatef(0, 0, 0)

    # Rotate to match IMU's current rotation.
    glRotatef(10, 1, 0, 0)
    glRotatef(20, 0, 1, 0)
    glRotatef(30, 0, 0, 1)

    # Draw the IMU.
    @box.draw

    # Remove the top of the stack of matrices, leaving the identity at the top.
    glPopMatrix
  end

end

FixedBoxExample.new("Box Example", 500, 500)
