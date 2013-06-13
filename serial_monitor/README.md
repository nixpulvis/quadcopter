## Ruby Serial Port Reader Goals

To read incoming data coming in as serial from USB.

For example, reading the output from a gyroscope on an arduino.

## Running Serial-monitor

cd into the serial_monitor folder
execute the program via:


`ruby bin/serial-monitor [serial port] [baud rate]`

For example:

`ruby bin/serial-monitor /dev/tty.usbmodem621 38400`

# Requirements

- Configurable serialport selection.
- Configurable Baud rate.
- Configurable start/stop byte for each message (default to \n).

# Example Usage (in bin/serial-monitor)

```ruby
SerialMonitor.open(ARGV[0], [Baud rade], [start character], [end character]) do |sm|
  [action to perform]
end
```
