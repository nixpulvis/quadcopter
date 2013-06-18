## Ruby Serial Port Reader Goals

To read incoming data coming in as serial from USB.

For example, reading the output from a gyroscope on an arduino.

## Running Serial-monitor

Usage:

`serial-monitor [serial port] [baud rate]`

For example:

`serial-monitor /dev/tty.usbmodem621 38400`

# Requirements

- Configurable serialport selection.
- Configurable Baud rate.

# Example API Usage

```ruby
SerialMonitor.open(file, baud) do |sm|
  # ...
end
```
