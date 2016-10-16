# Configuration variables.

# Microcontroller options.
DF_CPU ?= 16000000UL
MMCU   ?= atmega328p

# Port to flash to.
PORT ?= /dev/$(shell ls /dev/ | grep "tty\.usb" | sed -n 1p)

# UART baud rate.
# 115200 - Arduino Uno
# 57600  - Arduino Mini Pro
BAUD ?= 115200

# The language we're building from (C or Assembly), default is C.
LANGUAGE ?= c

# Libraries, defaults to all.
C_SRCS = $(wildcard src/*.c)
SRCS ?= $(C_SRCS:.c=)

################################

# Probably shouldn't touch these.

# The `gcc` executable.
CC = avr-gcc
C_FLAGS = -Wall -Werror -pedantic -Os -std=c99
C_HEADERS = -I. -I/usr/local/avr/include -I/usr/local/Cellar/avr-libc/2.0.0/avr/include

# The `as` executable.
AS = avr-as

# The `obj-copy` executable.
OBJ_COPY = avr-objcopy
OBJ_COPY_FLAGS = -O ihex -R .eeprom

# The `avrdude` executable.
AVRDUDE = avrdude
AVRDUDE_FLAGS = -F -V -c arduino -p ATMEGA328P

# The `avr-size` executable.
AVRSIZE = avr-size
AVRSIZE_FLAGS = -C

# List of tests.
TESTS = $(wildcard test/**/*.c)

################################

# The default rule is run with just `make`.

default: src/esc.o

################################

# Pseudo rules.

# These rules are not file based.
.PHONY: flash serial size clean

# flash
#
# Given a hex file using `avrdude` this target flashes the AVR with the
# new program contained in the hex file.
flash: $(TARGET).hex
	$(AVRDUDE) $(AVRDUDE_FLAGS) -P $(PORT) -b $(BAUD) -U flash:w:$<

# serial
#
# Open up a screen session for communication with the AVR
# through it's on-board UART.
serial:
	screen $(PORT) $(BAUD)

# size
#
# Show information about target's size.
size: $(TARGET).bin
	$(AVRSIZE) $(AVRSIZE_FLAGS) --mcu=$(MMCU) $<

# Remove non-source files.
clean:
	rm -rf \
		$(wildcard **/*.o) \
		$(wildcard **/*.bin) \
		$(wildcard **/*.hex) \
		$(wildcard test/**/*.hex) \

################################

# File rules.

# .bin <- .o
%.bin: %.o $(SRCS:=.o)
	$(CC) $(C_FLAGS) -mmcu=$(MMCU) $? -o $@ -lavrm

# .o <- .c
%.o: %.c
	$(CC) $(C_HEADERS) $(C_FLAGS) -DF_CPU=$(DF_CPU) -mmcu=$(MMCU) -c $< -o $@

# .hex <- .bin
%.hex: %.bin
	$(OBJ_COPY) $(OBJ_COPY_FLAGS) $< $@

################################

# Mark the hex file as intermediate.
.INTERMEDIATE: $(TARGET).hex $(TARGET).bin
