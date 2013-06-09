require 'serial_monitor'
require 'gel'
require 'imu_visualization/imu'

class IMUVisualization < Gel
  attr_reader :imu

  def setup
    initial_position = Position.new(0, 0, 0)
    initial_rotation = Rotation.new(0, 0, 0)
    @imu = IMU.new("MPU-9150", initial_position, initial_rotation)

    @serial_monitor = SerialMonitor.new('/dev/tty.usbmodem411', 38400, "\n")
    @active_mode = :acc

    @data = {
      :ax => 0, :ay => 0, :az => 0,
      :gx => 0, :gy => 0, :gz => 0,
      :mx => 0, :my => 0, :mz => 0,
    }

    # @cal = { :x => 0, :y => 0, :z => 0 }
    # @agg_gyro_x = 0
    # @agg_gyro_y = 0
    # @agg_gyro_z = 0
  end

  def loop
    set_data

    case @active_mode
    when :accel
      @imu.rotation.x, @imu.rotation.y, @imu.rotation.z = @data[:ax], @data[:ay], @data[:az]
    when :gyro
      x, z, y = @data[:gx], @data[:gy], @data[:gz]

      @agg_gyro_x += x  + @cal[:x]
      @agg_gyro_y += -y + @cal[:y]
      @agg_gyro_z += z  + @cal[:z]

      @imu.rotation.x, @imu.rotation.y, @imu.rotation.z = [@agg_gyro_x, @agg_gyro_y, @agg_gyro_z].map { |e| e /= 2000 }

    when :mag
      @imu.rotation.x, @imu.rotation.y, @imu.rotation.z = @data[:mx], @data[:my], @data[:mz]
    end

  end

  def draw
    # Make a copy of the identity matrix at the top of the stack.
    glPushMatrix

    # Move the corrdinate system based on IMU's position.
    glTranslatef(@imu.position.x, @imu.position.y, @imu.position.z)

    # Rotate to match IMU's current rotation.
    glRotatef(@imu.rotation.x, 1, 0, 0)
    glRotatef(@imu.rotation.y, 0, 1, 0)
    glRotatef(@imu.rotation.z, 0, 0, 1)

    # Draw the IMU.
    drawBox(0.35, 0.1, 0.45)

    # Remove the top of the stack of matrices, leaving the identity at the top.
    glPopMatrix
  end

  def keyboard(key, x, y)
    case key
    when 'c'
      @cal = { :x => -@data[:gx], :y => -@data[:gy], :z => -@data[:gz] }
    when 'a'
      @active_mode = :accel
      puts 'accel mode'
    when 'g'
      @active_mode = :gyro
      puts 'gyro mode'
    when 'm'
      @active_mode = :mag
      puts 'mag mode'
    when ' '
      p @cal

      puts <<-EOS
IMU (#{@imu.name})
  Position : X = #{@imu.position.x}, Y = #{@imu.position.y}, Z = #{@imu.position.z}
  Rotation : X = #{@imu.rotation.x}, Y = #{@imu.rotation.y}, Z = #{@imu.rotation.z}"
EOS
    when "\e"
      exit(0)
    end
  end

  private

  def update_data
    @data[:ax], @data[:ay], @data[:az],
    @data[:gx], @data[:gy], @data[:gz],
    @data[:mx], @data[:my], @data[:mz] = @serial_monitor.gets.split(" ").map { |e| e.to_i }
  end

end
