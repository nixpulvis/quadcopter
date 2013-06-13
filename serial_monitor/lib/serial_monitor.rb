require 'serialport'
require 'io/console'

class SerialMonitor < SerialPort
  def self.new(serial_port, baud)
    sp = super(serial_port, baud)
    sleep(0.1)
    sp.iflush
    sp
  end
end
