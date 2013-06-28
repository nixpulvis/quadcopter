class Gel
  class Box
    attr_accessor :position, :rotation, :width, :height, :depth, :colors

    def initialize(w, h, d, c = [0.5,0.5,0.5])
      @width, @height, @depth = w, h, d
      self.color = c
      @position  = { :x => 0, :y => 0, :z => 0 }
      @rotation  = { :x => 0, :y => 0, :z => 0 }
    end

    def color=(value)
      self.colors = {
        :front  => value.map { |e| e += 0.1 },
        :back   => value.map { |e| e += 0.1 },
        :left   => value,
        :right  => value,
        :top    => value.map { |e| e -= 0.1 },
        :bottom => value.map { |e| e -= 0.1 },
      }
    end

    def draw
      glRotatef(rotation[:x], 1, 0, 0)
      glRotatef(rotation[:y], 0, 1, 0)
      glRotatef(rotation[:z], 0, 0, 1)

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
