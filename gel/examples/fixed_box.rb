require 'gel'

class FixedBoxExample < Gel

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
    drawBox(0.35, 0.1, 0.45)

    # Remove the top of the stack of matrices, leaving the identity at the top.
    glPopMatrix
  end

end

FixedBoxExample.new("Box Example", 500, 500)
