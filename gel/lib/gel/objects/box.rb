class Gel
  class Box
    attr_accessor :width, :height, :depth, :colors

    def initialize(width, height, depth, colors = {})
      @width, @height, @depth, @colors = width, height, depth, colors
    end

    def draw
      glBegin(GL_QUADS)

      # Front surface.
      glNormal3d(0, 0, 1)
      glColor3f(*@colors[:front]) if @colors[:front]
      glVertex3f( @width, -@height, -@depth)
      glVertex3f( @width,  @height, -@depth)
      glVertex3f(-@width,  @height, -@depth)
      glVertex3f(-@width, -@height, -@depth)

      # Back surface.
      glNormal3d(0, 0, -1)
      glColor3f(*@colors[:back]) if @colors[:back]
      glVertex3f( @width, -@height, @depth)
      glVertex3f( @width,  @height, @depth)
      glVertex3f(-@width,  @height, @depth)
      glVertex3f(-@width, -@height, @depth)

      # Right surface.
      glNormal3d(1, 0, 0)
      glColor3f(*@colors[:right]) if @colors[:right]
      glVertex3f(@width, -@height, -@depth)
      glVertex3f(@width,  @height, -@depth)
      glVertex3f(@width,  @height,  @depth)
      glVertex3f(@width, -@height,  @depth)

      # Left surface.
      glNormal3d(-1, 0, 0)
      glColor3f(*@colors[:left]) if @colors[:left]
      glVertex3f(-@width, -@height,  @depth)
      glVertex3f(-@width,  @height,  @depth)
      glVertex3f(-@width,  @height, -@depth)
      glVertex3f(-@width, -@height, -@depth)

      # Top surface.
      glNormal3d(0, 1, 0)
      glColor3f(*@colors[:top]) if @colors[:top]
      glVertex3f( @width,  @height,  @depth)
      glVertex3f( @width,  @height, -@depth)
      glVertex3f(-@width,  @height, -@depth)
      glVertex3f(-@width,  @height,  @depth)

      # Bottom surface.
      glNormal3d(0, -1, 0)
      glColor3f(*@colors[:bottom]) if @colors[:bottom]
      glVertex3f( @width, -@height, -@depth)
      glVertex3f( @width, -@height,  @depth)
      glVertex3f(-@width, -@height,  @depth)
      glVertex3f(-@width, -@height, -@depth)

      glEnd
    end

  end
end
