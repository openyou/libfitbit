from .protocol import ANTReceiveException
from .libusb import ANTlibusb
import usb

class DynastreamANT(ANTlibusb):
    """Class that represents the Dynastream USB stick base, for
    garmin/suunto equipment. Only needs to set VID/PID.

    """
    VID = 0x0fcf
    PID = 0x1008
    NAME = "Dynastream"

class FitBitANT(ANTlibusb):
    """Class that represents the fitbit base. Due to the extra
    hardware to handle tracker connection and charging, has an extra
    initialization sequence.

    """

    VID = 0x10c4
    PID = 0x84c4
    NAME = "FitBit"

    def open(self, vid = None, pid = None):
        if not super(FitBitANT, self).open(vid, pid):
            return False
        self.init()
        return True
    
    def init(self):
        # Device setup
        # bmRequestType, bmRequest, wValue, wIndex, data
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        # At this point, we get a 4096 buffer, then start all over
        # again? Apparently doesn't require an explicit receive
        self._connection.ctrl_transfer(0x40, 0x00, 0x0, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x4A, 0x0, [])
        # Receive 1 byte, should be 0x2
        self._connection.ctrl_transfer(0xC0, 0xFF, 0x370B, 0x0, 1)
        self._connection.ctrl_transfer(0x40, 0x03, 0x800, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x13, 0x0, 0x0, \
                                       [0x08, 0x00, 0x00, 0x00,
                                        0x40, 0x00, 0x00, 0x00,
                                        0x00, 0x00, 0x00, 0x00,
                                        0x00, 0x00, 0x00, 0x00
                                        ])
        self._connection.ctrl_transfer(0x40, 0x12, 0x0C, 0x0, [])
        try:
            self._receive()
        except usb.USBError:
            pass
