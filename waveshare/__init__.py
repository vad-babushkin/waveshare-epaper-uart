#!/usr/bin/env python
# -*- coding: utf-8 -*-

''' Python module for Waveshare 4.3inch e-Paper UART Module

This module facilitates orchestrating the Waveshare 800x600, 4.3 inch e-Paper
UART Module.

Throughout the documentation, references will be made to a wiki, it's this one:

    https://www.waveshare.com/wiki/4.3inch_e-Paper_UART_Module#Serial_port

Specifically as fetched on Nov 11, 2017.

'''

#pylint: disable=line-too-long

from __future__ import print_function

import RPi.GPIO as GPIO
import serial
import struct


# These correspond to the board pins used on the PI3:
PIN_RESET = 3
PIN_WAKEUP = 7

def _do_checksum(data):
    '''
    Creates a checksum by xor-ing every byte of (byte string) data.
    '''
    checksum = 0
    for byte in data:
        checksum = checksum ^ ord(byte)
    return chr(checksum)

class Command(object):
    '''
    Commands used by the e ink display have a certain format that easily lends
    itself to objectification, so this is the base class for those commands.

    Child classes should only need to call the constructor of this class and provide the new command and data content.
    '''

    FRAME_HEADER = b'\xa5'
    FRAME_FOOTER = b'\xcc\x33\xc3\x3c'
    HEADER_LENGTH = 1
    COMMAND_LENGTH = 1
    LENGTH_LENGTH = 2
    FOOTER_LENGTH = 4
    CHECK_LENGTH = 1
    COMMAND = '\x00'

    def __init__(self, command=None, data=None):
        self.command = command or self.COMMAND
        self.bytes = data or []

    def calculate_length(self):
        '''
        Calculate the total length of the packet and returns it as a number
        (*NOT* formatted like the packet requires!).
        '''
        return Command.HEADER_LENGTH + Command.LENGTH_LENGTH + Command.COMMAND_LENGTH + len(self.bytes) + Command.FOOTER_LENGTH + Command.CHECK_LENGTH


    def convert_bytes(self):
        '''
        Conver the internal bytes into a string, not the human readable sort,
        but the sort to be used by the protocol.
        '''
        return ''.join(self.bytes)

    def _encode_packet(self):
        '''
        Encodes and returns the entire packet in a format that is suitable for
        transmitting over the serial connection.
        '''
        return Command.FRAME_HEADER + struct.pack('>H', self.calculate_length()) + self.command + self.convert_bytes() + Command.FRAME_FOOTER


    def encode(self):
        '''
        Encodes the packet and attaches the checksum.
        '''
        packet = self._encode_packet()
        return packet + _do_checksum(packet)

    def __repr__(self):
        '''
        Returns a human readable string of hex digits corresponding to the
        encoded full packet content.
        '''
        return u' '.join([u'%02x' % ord(b) for b in self.encode()])

class Handshake(Command):
    '''
    Handshake or Null command.

    From the wiki:

    > Handshake command. If the module is ready, it will return an "OK".

    '''

class SetBaudrate(Command):
    '''
    From the wiki:

    Set the serial Baud rate.

    After powered[sic] up, the default Baud rate is 115200. This command is
    used to set the Baud rate. You may need to wait 100ms for the module to
    return the result after sending this command, since the host may take a
    period of time to change its Baud rate.
    '''
    COMMAND = '\x01'

    def __init__(self, baud):
        super(SetBaudrate, self).__init__(SetBaudrate.COMMAND, struct.pack('>L', baud))


class ReadBaudrate(Command):
    '''
    From the wiki:

    Return the current Baud rate value in ASCII format.

    '''
    COMMAND = '\x02'

class ReadStorageMode(Command):
    '''
    From the wiki:
    Return the information about the currently used storage area.

    0: NandFlash

    1: MicroSD
    '''
    COMMAND = '\x06'

class SetStorageMode(Command):
    '''
    From the wiki:

    Set the storage area to select the storage locations of font library and
    images, either the external TF card or the internal NandFlash is available.
    '''
    COMMAND = b'\x07'
    NAND_MODE = b'\x00'
    TF_MODE = b'\x01'

    def __init__(self, target=NAND_MODE):
        super(SetStorageMode, self).__init__(SetStorageMode.COMMAND, data=[target])

class SleepMode(Command):
    '''
    GPIO must be used to wake it back up.

    From the wiki:
    The system will enter the sleep mode and reduce system power consumption by this command. Under sleep mode, the state indicator is off, and the system does not respond any commands. Only the rising edge on the pin WAKE_UP can wake up the system. 
    '''
    COMMAND = b'\x08'

class RefreshAndUpdate(Command):
    '''
    From the wiki:
    Refresh and update the display at once.
    '''
    COMMAND = b'\x0a'

class CurrentDisplayRotation(Command):
    '''
    From the wiki:
    Return the current display direction

    0: Normal

    1 or 2: 180° rotation (depending on Firmware)
    '''
    COMMAND = b'\x0c'

class SetCurrentDisplayRotation(Command):
    '''
    From the wiki:
    Set the display direction, only 180° rotation display supported.

    0x00: Normal

    0x01 or 0x02: 180° rotation (depending on Firmware)
    '''
    COMMAND = b'\x0d'
    NORMAL = b'\x00'
    FLIP = b'\x01'
    FLIPB = b'\x02' # depending on firmware, value could be this...
    def __init__(self, rotation=NORMAL):
        super(SetCurrentDisplayRotation, self).__init__(SetCurrentDisplayRotation.COMMAND, rotation)

class ImportFontLibrary(Command):
    '''
    From the wiki:
    Import font library: 48MB

    Import the font library files from the TF card to the internal NandFlash.
    The font library files include GBK32.FON/GBK48.FON/GBK64.FON. The state
    indicator will flicker 3 times when the importation is start and ending.
    '''
    COMMAND = b'\x0e'

class ImportImage(Command):
    '''
    From the wiki:
    Import image: 80MB
    '''
    COMMAND = b'\x0f'
    def __init__(self):
        super(ImportImage, self).__init__(ImportImage.COMMAND)

class DisplayText(Command):
    '''
    Any text to display needs to be GB2312 encoded.  For example:

        DisplayText(10, 10, u'你好World'.encode('gb2312'))

    From the wiki:
    Display a character string on a specified coordination position. Chinese
    and English mixed display is supported.
    '''
    COMMAND = b'\x30'
    def __init__(self, x, y, text):
        super(DisplayText, self).__init__(self.COMMAND, struct.pack(">HH", x, y) + text + '\x00')

class DisplayImage(DisplayText):
    '''
    From the wiki:
    Before executing this command, please make sure the bitmap file you want to display is stored in the storage area (either TF card or internal NandFlash).

    Example: A5 00 16 70 00 00 00 00 50 49 43 37 2E 42 4D 50 00 CC 33 C3 3C DF

    Descriptions: Image start coordination position: (0x00, 0x00)

    0x50 49 43 37 2E 42 4D 50: Bitmap name: PIC7.BMP

    Each character string should be end with a "0". So, you should add a "00" at the end of the string 50 49 43 37 2E 42 4D 50.

    The name of the bitmap file should be in uppercase English character(s). And the string length of the bitmap name should be less than 11 characters, in which the ending "0" is included. For example, PIC7.BMP and PIC789.BMP are correct bitmap names, while PIC7890.BMP is a wrong bitmap namem.
    '''
    COMMAND = b'\x70'

class SetPallet(Command):
    '''
    From the wiki:
    Set the foreground color and the background color on drawing, in which the
    foreground color can be used to display the basic drawings and text, while
    the background color is used to clear the screen.
    '''
    COMMAND = b'\x10'
    BLACK = b'\x00'
    DARK_GRAY = b'\x01'
    LIGHT_GRAY = b'\x02'
    WHITE = b'\x03'
    def __init__(self, fg=BLACK, bg=WHITE):
        fg = fg or SetPallet.BLACK
        bg = bg or SetPallet.WHITE
        super(SetPallet, self).__init__(SetPallet.COMMAND, [fg, bg])

class GetPallet(Command):
    '''
    From the wiki:
    For example, when returns "03", "0" means the foreground color is Black and
    "3" means the background color is White.
    '''
    COMMAND = b'\x11'

class SetFontSize(Command):
    '''
    Common parent for font size setting commands.
    '''
    THIRTYTWO = b'\x01'
    FOURTYEIGHT = b'\x02'
    SIXTYFOUR = b'\x03'
    def __init__(self, command, size=THIRTYTWO):
        super(SetFontSize, self).__init__(command, [size])

class SetEnFontSize(SetFontSize):
    '''
    From the wiki:
    Set the English font size (0x1E or 0x1F, may differ depending on version).
    '''
    COMMAND = b'\x1e'
    def __init__(self, size=SetFontSize.THIRTYTWO):
        super(SetEnFontSize, self).__init__(SetEnFontSize.COMMAND, size)

class SetZhFontSize(SetFontSize):
    '''
    From the wiki:
    Set the Chinese font size (0x1F).
    '''
    COMMAND = b'\x1f'
    def __init__(self, size=SetEnFontSize.THIRTYTWO):
        super(SetZhFontSize, self).__init__(SetZhFontSize.COMMAND, size)

class DrawCircle(Command):
    '''
    From the wiki:
    Draw a circle based on the given center coordination and radius.
    '''
    COMMAND = b'\x26'
    def __init__(self, x, y, radius):
        super(DrawCircle, self).__init__(self.COMMAND, struct.pack(">HHH", x, y, radius))

class FillCircle(DrawCircle):
    '''
    From the wiki:
    Fill a circle based on the given center coordination and radius.
    '''
    COMMAND = b'\x27'

class DrawTriangle(Command):
    '''
    From the wiki:
    Draw a tri-angle according to three given point coordinates.
    '''
    COMMAND = b'\x28'
    def __init__(self, x1, y1, x2, y2, x3, y3):
        super(DrawTriangle, self).__init__(self.COMMAND, struct.pack(">HHHHHH", x1, y1, x2, y2, x3, y3))

class FillTriangle(DrawTriangle):
    '''
    From the wiki:
    Fill a tri-angle according to three given point coordinates.
    '''
    COMMAND = b'\x29'

class ClearScreen(Command):
    '''
    From the wiki:
    Clear the screen with the background color.
    '''
    COMMAND = b'\x2e'



class EPaper(object):
    '''
    This is a class to make interacting with the 4.3inch e-Paper UART Module
    easier.

    See https://www.waveshare.com/wiki/4.3inch_e-Paper_UART_Module#Serial_port
    for more info.
    '''
    def __init__(self, port, auto=False, reset=PIN_RESET, wakeup=PIN_WAKEUP, mode=GPIO.BOARD):
        '''
        Makes an EPaper object that will read and write from the specified
        serial device (file name).

        Note: This class makes use of the Raspberry PI GPIO functions, the
        caller should invoke GPIO.cleanup() before exiting.

        @param port The file name to open.
        @param auto Automatically update after each call.
        @param reset The GPIO pin to use for resets.
        @param wakeup The GPIO pin to use for wakeups.
        @param mode The mode of GPIO pin addressing (GPIO.BOARD is the default).
        '''
        self.serial = serial.Serial(port)
        self.serial.baudrate = 115200 # default for device
        self.serial.bytesize = serial.EIGHTBITS
        self.serial.parity = serial.PARITY_NONE

        GPIO.setmode(mode)
        GPIO.setup(reset, GPIO.OUT)
        GPIO.setup(wakeup, GPIO.OUT)

        self.reset_pin = reset
        self.wakeup_pin = wakeup
        self.auto = auto

    def __enter__(self):
        '''
        So the EPaper class can be used in a with clause and
        handle cleaning up the GPIO stuff on exit.  It returns itself.
        '''
        return self

    def __exit__(self ,type, value, traceback):
        '''
        Invokes the GPIO.cleanup() method.  If that's not a desired behavior,
        don't use the with clause.
        '''
        GPIO.cleanup()


    def reset(self):
        '''
        Reset the display by setting the reset pin to high and then low.
        '''
        GPIO.output(self.reset_pin, GPIO.HIGH)
        GPIO.output(self.reset_pin, GPIO.LOW)

    def sleep(self):
        '''
        Tell the display to go to sleep.
        '''
        self.serial.write(SleepMode().encode())

    def wake(self):
        '''
        Tell the device to wake up.  It only makes sense to do this after
        telling it to sleep.
        '''
        GPIO.output(self.wakeup_pin, GPIO.HIGH)
        GPIO.output(self.wakeup_pin, GPIO.LOW)

    def update(self):
        '''
        Update the display.
        '''
        self.serial.write(RefreshAndUpdate().encode())

    def send(self, command):
        '''
        Send the provided command to the device, does not wait for a response
        or sleep or make any other considerations.
        '''
        self.serial.write(command.encode())
        if self.auto:
            self.serial.write(RefreshAndUpdate().encode())

    def read(self, size=100, timeout=5):
        '''
        Read a response from the underlying serial device.
        '''
        self.serial.timeout = timeout
        return self.serial.read(size)

if __name__ == "__main__":
    try:
        paper = EPaper('/dev/ttyS1')
        print('Handshake')
        paper.send(Handshake())
        print(paper.read(2))

        paper.send(ClearScreen())

        paper.send(SetZhFontSize(SetZhFontSize.THIRTYTWO))
        paper.send(DisplayText(10,10, u'你好, World'.encode('gb2312')))
        print('Hello World 1')
        print(paper.read(2))
        print('Setting pallet to DARK_GRAY/white')
        paper.send(SetPallet(SetPallet.DARK_GRAY))
        print(paper.read(2))
        paper.send(DisplayText(60, 60, u'Hello, World'.encode('utf-8')))
        print('Hello World 2')
        print(paper.read(2))
        print('Setting pallet to LIGHT_GRAY/black')
        paper.send(SetPallet(SetPallet.LIGHT_GRAY, SetPallet.BLACK))
        print(paper.read(2))
        paper.send(DisplayText(120, 120, u'こんにちわ, World'.encode('gb2312')))
        print('Hello World 3')
        print(paper.read(2))
        print('Setting pallet to LIGHT_GRAY/white')
        paper.send(SetPallet(SetPallet.LIGHT_GRAY))
        print(paper.read(2))
        paper.send(DisplayText(240, 0, u'Здравствуй, Мiр!'.encode('gb2312')))
        print('Hello World 4')
        print(paper.read(2))
        paper.update()

#        print(u'%s' % Handshake())
#        print(u'%s' % SetBaudrate(9600))
#        print(u'%s' % ReadBaudrate())
#        print(u'%s' % ReadStorageMode())
#        print(u'%s' % SetStorageMode(SetStorageMode.TF_MODE))
#        print(u'%s' % SleepMode())
#        print(u'%s' % RefreshAndUpdate())
#        print(u'%s' % CurrentDisplayRotation())
#        print(u'%s' % SetCurrentDisplayRotation(SetCurrentDisplayRotation.NORMAL))
#        print(u'%s' % ImportFontLibrary())
#        print(u'%s' % ImportImage())
#        print(u'%s' % DisplayText(10, 10, u'你好, World'.encode('gb2312')))
#        print(u'%s' % DisplayText(60, 60, u'Hello, World'.encode('utf-8')))
#        print(u'%s' % DisplayText(120, 120, u'こんにちわ, World'.encode('utf-8')))
#        print(u'%s' % SetEnFontSize(SetEnFontSize.SIXTYFOUR))
        print(paper.read())

    finally:
        GPIO.cleanup()
