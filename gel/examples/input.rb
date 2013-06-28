require 'bundler/setup'
require 'gel'

module Examples
  class Input < Gel

    def setup
      @mode = :keyboard
      @box  = Box.new 0.45, 0.35, 0.25, [0.75, 0.1, 0.1]
    end

    def draw
      @box.draw
    end

    def mouse_move(x, y)
      if @mode == :mouse
        rotate_based_on_mouse(x, y)
      end
    end

    def keyboard(key, x, y)
      case key
      when 'r'
        @box.rotation[:z] -= 10
      when 'l'
        @box.rotation[:z] += 10
      when 'm'
        @mode = @mode == :keyboard ? :mouse : :keyboard
        rotate_based_on_mouse(x, y)
        puts "Activated #{@mode} mode."
      end
    end

    def special_keyboard(key, x, y)
      if @mode == :keyboard
        case key
        when GLUT_KEY_UP
          @box.rotation[:x] += 10
        when GLUT_KEY_DOWN
          @box.rotation[:x] -= 10
        when GLUT_KEY_LEFT
          @box.rotation[:y] += 10
        when GLUT_KEY_RIGHT
          @box.rotation[:y] -= 10
        end
      end
    end

    private

    def rotate_based_on_mouse(x, y)
      scale = 2

      @box.rotation = {
        :x => -y/scale,
        :y => x/scale,
        :z => @box.rotation[:z],
      }
    end

  end
end

puts <<-EOL
Use the arrow keys and 'r'/'l' to rotate the box. Or click 'm' to toggle mouse
following.
EOL
Examples::Input.new("Input Example", 500, 500)
