require 'serialport'
require 'io/console'

class SerialMonitor < SerialPort
  def self.new(serial_port, baud)
    sp = super(serial_port, baud)

    # http://www.linuxforums.org/
    #   forum/miscellaneous/130106-tcflush-not-flushing-serial-port.html
    sleep(0.1)

    # http://www.ruby-doc.org/stdlib-2.0/libdoc/
    #   io/console/rdoc/IO.html#method-i-iflush
    #
    # Calls tcflush(fd, TCIFLUSH), just what we need.
    sp.iflush

    sp
  end
end
