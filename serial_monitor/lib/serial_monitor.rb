require 'serialport'

class SerialMonitor
  attr_reader :serial_port, :baud
  attr_accessor :start_byte, :stop_byte

  def initialize(serial_port, baud, start_byte, stop_byte = start_byte)
    @serial_port = serial_port
    @baud = baud
    @start_byte = start_byte
    @stop_byte = stop_byte

    # Initialize SerialPort from gem.
    @sp = SerialPort.new(serial_port, baud)
  end


  def self.open(serial_port, baud, start_byte, stop_byte = start_byte)
    sm = SerialMonitor.new(serial_port, baud, start_byte, stop_byte)

    if block_given?
      yield sm
      sm.close
    else
      sm
    end
  end

  def gets
    begin
      until @sp.getc == start_byte; end
      @sp.gets(stop_byte).gsub(stop_byte, "")
    rescue ArgumentError => e
      warn "Error parsing serial,` #{e.message}."
    end
  end

  def close
    @sp.close
  end
end
