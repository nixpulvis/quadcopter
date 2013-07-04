require 'serial_monitor'
require 'gel'

class IMUVisualization < Gel

  def setup
    @serial_monitor = SerialMonitor.new(ARGV[0], 38400)
    update
  end

  def loop
    update
  end

  def draw
    glMultMatrixf(@data);

    glBegin(GL_QUADS)

    color  = [0, 0.1, 0.75]
    colors = {
      :front  => color.map { |e| e += 0.1 },
      :back   => color.map { |e| e += 0.1 },
      :left   => color,
      :right  => color,
      :top    => color.map { |e| e -= 0.1 },
      :bottom => color.map { |e| e -= 0.1 },
    }

    width  = 0.5
    height = 0.2
    depth  = 0.65

    glColor3f(*colors[:front])
    glVertex3f( width, -height, -depth)
    glVertex3f( width,  height, -depth)
    glVertex3f(-width,  height, -depth)
    glVertex3f(-width, -height, -depth)

    glColor3f(*colors[:back])
    glVertex3f( width, -height, depth)
    glVertex3f( width,  height, depth)
    glVertex3f(-width,  height, depth)
    glVertex3f(-width, -height, depth)

    glColor3f(*colors[:right])
    glVertex3f(width, -height, -depth)
    glVertex3f(width,  height, -depth)
    glVertex3f(width,  height,  depth)
    glVertex3f(width, -height,  depth)

    glColor3f(*colors[:left])
    glVertex3f(-width, -height,  depth)
    glVertex3f(-width,  height,  depth)
    glVertex3f(-width,  height, -depth)
    glVertex3f(-width, -height, -depth)

    glColor3f(*colors[:top])
    glVertex3f( width,  height,  depth)
    glVertex3f( width,  height, -depth)
    glVertex3f(-width,  height, -depth)
    glVertex3f(-width,  height,  depth)

    glColor3f(*colors[:bottom])
    glVertex3f( width, -height, -depth)
    glVertex3f( width, -height,  depth)
    glVertex3f(-width, -height,  depth)
    glVertex3f(-width, -height, -depth)

    glEnd
  end

  private

  def update
    w, x, z, y = @serial_monitor.gets.split("\t").map { |e| e.to_f }

    # save the matrix form of this quaternion
    @data = [
      [1.0 - 2.0*y*y - 2.0*z*z, 2.0*x*y - 2.0*z*w, 2.0*x*z + 2.0*y*w, 0.0],
      [2.0*x*y + 2.0*z*w, 1.0 - 2.0*x*x - 2.0*z*z, 2.0*y*z - 2.0*x*w, 0.0],
      [2.0*x*z - 2.0*y*w, 2.0*y*z + 2.0*x*w, 1.0 - 2.0*x*x - 2.0*y*y, 0.0],
      [0.0, 0.0, 0.0, 1.0]
    ]
  end

end
